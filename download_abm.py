#!/usr/bin/env python3
"""Download ABM JUNE 2026 videos — single-threaded, disk-aware, checksums, metadata."""
import csv, hashlib, json, os, shutil, subprocess, sys, time, requests
from datetime import datetime, timezone
from pathlib import Path

MANIFEST = "/tmp/classplus_abm_manifest.json"
TOKEN_FILE = "/tmp/classplus_manifest.json"
OUTPUT_DIR = os.path.expanduser("~/development/classplus-dl/videos/ABM JUNE 2026")
PROGRESS = os.path.expanduser("~/development/classplus-dl/abm_progress.json")
META_CSV = os.path.expanduser("~/development/classplus-dl/abm_metadata.csv")
META_JSON = os.path.expanduser("~/development/classplus-dl/abm_metadata.json")
DELAY = 3
MIN_FREE_GB = 5

def load_token():
    return json.load(open(TOKEN_FILE))["token"]

def load_videos():
    return json.load(open(MANIFEST))

def load_progress():
    if os.path.exists(PROGRESS):
        return set(json.load(open(PROGRESS)).get("done", []))
    return set()

def save_progress(done):
    with open(PROGRESS, "w") as f:
        json.dump({"done": sorted(done)}, f)

def load_metadata():
    if os.path.exists(META_JSON):
        return json.load(open(META_JSON))
    return []

def save_metadata(records):
    with open(META_JSON, "w") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    # Also write CSV
    if records:
        with open(META_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=records[0].keys())
            w.writeheader()
            w.writerows(records)

def disk_free_gb(path):
    return shutil.disk_usage(path).free / (1024**3)

def sanitize(name):
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")
    return name[:180]

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def resolve_url(chash, token):
    r = requests.get(
        "https://api.classplusapp.com/cams/uploader/video/jw-signed-url",
        params={"contentId": chash},
        headers={
            "x-access-token": token, "region": "IN",
            "Origin": "https://web.classplusapp.com",
            "Referer": "https://web.classplusapp.com/",
        },
        timeout=15,
    )
    d = r.json()
    if d.get("success") is not True:
        raise RuntimeError(f"API: {d.get('message', d)}")
    return d["url"]

def download(signed_url, outpath):
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning", "-stats",
        "-i", signed_url, "-c", "copy", "-bsf:a", "aac_adtstoasc",
        str(outpath),
    ], check=True)

def main():
    videos = load_videos()
    token = load_token()
    done = load_progress()
    meta = load_metadata()
    meta_by_hash = {m["contentHashId"]: m for m in meta}

    print(f"ABM videos: {len(videos)}")
    print(f"Already done: {len(done)}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Metadata: {META_CSV}")
    print(f"Stop if < {MIN_FREE_GB}GB free\n")

    total_done = len(done)
    new_records = []

    for i, v in enumerate(videos):
        chash = v["contentHashId"]
        if chash in done:
            # Already tracked — but check metadata completeness
            if chash not in meta_by_hash:
                # Metadata missing, try to reconstruct from disk
                rel_path = v["folder_path"].replace("ABM JUNE 2026/", "", 1)
                out_dir = os.path.join(OUTPUT_DIR, *[sanitize(p) for p in rel_path.split("/")])
                out_file = os.path.join(out_dir, sanitize(v["name"]) + ".mp4")
                if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                    size = os.path.getsize(out_file)
                    csum = sha256_file(out_file)
                    rec = {
                        "name": v["name"], "folder": v["folder_path"],
                        "duration": v.get("duration",""), "contentHashId": chash,
                        "file_path": out_file, "file_size_bytes": size,
                        "sha256": csum, "downloaded_at": datetime.now(timezone.utc).isoformat(),
                    }
                    new_records.append(rec)
                    meta_by_hash[chash] = rec
                    print(f"[meta fix] {v['name'][:80]} → sha256={csum[:16]}...")
            continue

        name = v["name"]
        rel_path = v["folder_path"].replace("ABM JUNE 2026/", "", 1)
        out_dir = os.path.join(OUTPUT_DIR, *[sanitize(p) for p in rel_path.split("/")])
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, sanitize(name) + ".mp4")

        total_done += 1
        free = disk_free_gb(out_dir)
        print(f"\n[{total_done}/285] {name[:110]}")
        print(f"  folder: {rel_path}")
        print(f"  disk free: {free:.1f} GB")

        if free < MIN_FREE_GB:
            print(f"  ⚠  < {MIN_FREE_GB}GB free — stopping.")
            break

        if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
            print(f"  → file exists, computing checksum...")
            size = os.path.getsize(out_file)
            csum = sha256_file(out_file)
            print(f"  ✓ skip — {size/(1024**2):.0f}MB  sha256={csum[:16]}...")
            done.add(chash)
            rec = {
                "name": name, "folder": v["folder_path"],
                "duration": v.get("duration",""), "contentHashId": chash,
                "file_path": out_file, "file_size_bytes": size,
                "sha256": csum, "downloaded_at": datetime.now(timezone.utc).isoformat(),
            }
            new_records.append(rec)
            meta_by_hash[chash] = rec
            save_progress(done)
            continue

        try:
            signed = resolve_url(chash, token)
            download(signed, out_file)
            size = os.path.getsize(out_file)
            csum = sha256_file(out_file)
            print(f"  ✓ {size/(1024**2):.0f}MB  sha256={csum[:16]}...")
            done.add(chash)
            rec = {
                "name": name, "folder": v["folder_path"],
                "duration": v.get("duration",""), "contentHashId": chash,
                "file_path": out_file, "file_size_bytes": size,
                "sha256": csum, "downloaded_at": datetime.now(timezone.utc).isoformat(),
            }
            new_records.append(rec)
            meta_by_hash[chash] = rec
            save_progress(done)
        except Exception as e:
            msg = str(e)[:300]
            print(f"  ✗ {msg}")
            if any(kw in msg.lower() for kw in ("401", "token", "expired", "unauthorized")):
                print("\n[!] Token expired. Refresh and re-run.")
                break

        # Save metadata incrementally every 5 downloads
        if total_done % 5 == 0:
            all_meta = list(meta_by_hash.values())
            save_metadata(all_meta)

        if total_done < 285:
            time.sleep(DELAY)

    # Final save
    all_meta = list(meta_by_hash.values()) + new_records
    # Deduplicate by contentHashId
    seen = set()
    final = []
    for r in all_meta:
        if r["contentHashId"] not in seen:
            seen.add(r["contentHashId"])
            final.append(r)
    save_metadata(final)

    print(f"\n{'='*50}")
    print(f"Done: {len(done)}/{len(videos)}")
    print(f"Metadata: {META_JSON} | {META_CSV}")

if __name__ == "__main__":
    main()
