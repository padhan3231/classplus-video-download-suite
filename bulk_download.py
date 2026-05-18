#!/usr/bin/env python3
"""
bulk_download.py — Downloads all 1001 videos from course 696969.
Resumes from where it left off. Safe: 3s delay, single-threaded, same headers as browser.

Usage:
  python3 bulk_download.py [--output-dir ~/classplus_videos] [--start-from N]

Requires: ffmpeg in PATH
"""

import json
import os
import subprocess
import sys
import time
import requests
from pathlib import Path
from urllib.parse import quote

# ── Config ──────────────────────────────────────────────────────────
MANIFEST = "/tmp/classplus_video_manifest.json"
TOKEN_FILE = "/tmp/classplus_manifest.json"
OUTPUT_DIR = os.path.expanduser("~/development/classplus-dl/videos")
PROGRESS_FILE = os.path.expanduser("~/development/classplus-dl/download_progress.json")
DELAY_SECONDS = 3  # between downloads — be gentle

def load_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)["token"]

def load_manifest():
    with open(MANIFEST) as f:
        return json.load(f)["videos"]

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return set(json.load(f).get("downloaded", []))
    return set()

def save_progress(downloaded):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"downloaded": list(downloaded)}, f)

def sanitize_filename(name):
    """Replace characters unsafe for filenames."""
    unsafe = '<>:"/\\|?*'
    for ch in unsafe:
        name = name.replace(ch, "_")
    return name[:200]  # limit length

def resolve_signed_url(content_hash_id, token):
    """Call jw-signed-url API, return signed m3u8 URL."""
    resp = requests.get(
        "https://api.classplusapp.com/cams/uploader/video/jw-signed-url",
        params={"contentId": content_hash_id},
        headers={
            "x-access-token": token,
            "region": "IN",
            "Origin": "https://web.classplusapp.com",
            "Referer": "https://web.classplusapp.com/",
        },
        timeout=15,
    )
    data = resp.json()
    if data.get("success") is not True:
        raise RuntimeError(f"API error: {data.get('message', data)}")
    url = data.get("url", "")
    if not url:
        raise RuntimeError("No URL in response")
    return url

def download_video(signed_url, output_path):
    """Download HLS stream with ffmpeg stream-copy to mp4."""
    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "warning", "-stats",
        "-i", signed_url,
        "-c", "copy", "-bsf:a", "aac_adtstoasc",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Print relevant error lines
        stderr_lines = result.stderr.strip().split("\n")
        relevant = [l for l in stderr_lines if "error" in l.lower() or "Error" in l or "403" in l or "401" in l]
        if not relevant:
            relevant = stderr_lines[-5:]
        raise RuntimeError(f"ffmpeg failed:\n" + "\n".join(relevant))

def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    print("Loading...")
    videos = load_manifest()
    token = load_token()
    downloaded = load_progress()

    print(f"Total videos: {len(videos)}")
    print(f"Already downloaded: {len(downloaded)}")
    print(f"Output: {output_dir}")
    print(f"Delay: {DELAY_SECONDS}s between downloads")
    print()

    remaining = len(videos) - len(downloaded)
    current = 0

    for i, v in enumerate(videos):
        video_index = i  # 0-based index as stable identifier
        if video_index in downloaded:
            continue

        name = v["name"]
        folder = v["folder_path"]
        content_hash = v["contentHashId"]
        duration = v.get("duration", "?")

        current += 1
        remaining -= 1
        print(f"[{current}/{len(videos)-len(downloaded)+current}] ({duration}) {name[:90]}")
        print(f"       {folder}")

        # Build output path preserving folder structure
        safe_folder = os.path.join(*[sanitize_filename(p) for p in folder.split("/")])
        safe_name = sanitize_filename(name) + ".mp4"
        out_dir = os.path.join(output_dir, safe_folder)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, safe_name)

        # Skip if file already exists on disk
        if os.path.exists(out_path):
            print(f"       → file exists, skipping")
            downloaded.add(video_index)
            save_progress(downloaded)
            continue

        try:
            signed_url = resolve_signed_url(content_hash, token)
            download_video(signed_url, out_path)

            # Verify file was created and has size > 0
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                size_mb = os.path.getsize(out_path) / (1024 * 1024)
                print(f"       ✓ {size_mb:.1f} MB")
                downloaded.add(video_index)
                save_progress(downloaded)
            else:
                print(f"       ✗ file empty/missing")
        except Exception as e:
            print(f"       ✗ ERROR: {e}")
            # Token might be expired
            if "401" in str(e) or "token" in str(e).lower() or "expired" in str(e).lower():
                print("\n[!] Token may be expired. Refresh CLASSPLUS_TOKEN and re-run.")
                print(f"[!] Progress saved. Resume from video {video_index + 1}.")
                return

        # Delay between downloads
        if remaining > 0:
            time.sleep(DELAY_SECONDS)

    print(f"\n{'='*50}")
    print(f"DONE. Downloaded: {len(downloaded)}/{len(videos)}")
    print(f"Output: {output_dir}")

if __name__ == "__main__":
    main()
