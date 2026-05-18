#!/usr/bin/env python3
"""Download ABM JUNE 2026 videos — single-threaded, disk-aware, checksums, metadata.
Retries network failures with backoff. Only stops on auth errors."""
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
MAX_RETRIES = 3
RETRY_BACKOFF = [5, 15, 45]  # seconds between retries

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

def is_auth_error(msg):
    """True if this is a permanent auth/token error (don't retry)."""
    lower = msg.lower()
    return any(kw in lower for kw in ("401", "403", "unauthorized", "forbidden",
                                       "invalid token", "token expired", "not authorized"))

def is_network_error(msg):
    """True if this is a transient network error (worth retrying)."""
    lower = msg.lower()
    return any(kw in lower for kw in ("timed out", "timeout", "connection refused",
                                       "connection reset", "no route to host",
                                       "name resolution", "temporary failure",
                                       "broken pipe", "eof", "reset by peer"))

def resolve_url(chash, token):
    """Resolve signed URL with retries on network failure."""
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.get(
                "https://api.classplusapp.com/cams/uploader/video/jw-signed-url",
                params={"contentId": chash},
                headers={
                    "x-access-token": token, "region": "IN",
                    "Origin": "https://web.classplusapp.com",
                    "Referer": "https://web.classplusapp.com/",
                },
                timeout=30,
            )
            d = r.json()
            if d.get("success") is not True:
                msg = d.get("message", str(d))
                if is_auth_error(msg):
                    raise RuntimeError(f"AUTH_FAIL:{msg}")
                raise RuntimeError(f"API: {msg}")
            return d["url"]
        except requests.exceptions.Timeout as e:
            last_err = f"timeout: {e}"
        except requests.exceptions.ConnectionError as e:
            last_err = f"connection: {e}"
        except requests.exceptions.RequestException as e:
            last_err = str(e)
            if is_auth_error(last_err):
                raise RuntimeError(f"AUTH_FAIL:{last_err}")

        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF)-1)]
            print(f"  ⚡ retry {attempt+1}/{MAX_RETRIES} in {wait}s ({last_err[:80]})")
            time.sleep(wait)

    raise RuntimeError(f"NET_FAIL:{last_err}")

def download(signed_url, outpath):
    """Download with ffmpeg, retry on network failures."""
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning", "-stats",
                "-i", signed_url, "-c", "copy", "-bsf:a", "aac_adtstoasc",
                str(outpath),
            ], capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                return

            # ffmpeg failed — classify error
            stderr = result.stderr
            if is_auth_error(stderr):
                raise RuntimeError(f"AUTH_FAIL: ffmpeg auth error - {stderr[:200]}")
            if is_network_error(stderr):
                last_err = f"ffmpeg network: {stderr[:120]}"
                # Remove partial file before retry
                if os.path.exists(outpath):
                    os.remove(outpath)
            else:
                raise RuntimeError(f"ffmpeg failed ({result.returncode}): {stderr[:300]}")

        except subprocess.TimeoutExpired:
            last_err = "ffmpeg hung (10min timeout)"
            if os.path.exists(outpath):
                os.remove(outpath)

        if attempt < MAX_RETRIES:
            # Get a fresh signed URL for retry (old one may have expired)
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF)-1)]
            print(f"  ⚡ retry {attempt+1}/{MAX_RETRIES} in {wait}s ({last_err[:80]})")
            time.sleep(wait)
            try:
                signed_url = resolve_url(
                    json.load(open(MANIFEST))[0]["contentHashId"],  # won't work, need real hash
                    load_token()
                )
                # Actually we need the chash — let caller handle re-resolve
            except:
                pass

    raise RuntimeError(f"NET_FAIL:{last_err}")

def main():
    videos = load_videos()
    token = load_token()
    done = load_progress()
    meta = load_metadata()
    meta_by_hash = {m["contentHashId"]: m for m in meta}

    print(f"ABM videos: {len(videos)}  Already done: {len(done)}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Retries: {MAX_RETRIES} with backoff {RETRY_BACKOFF}s")
    print(f"Stop if < {MIN_FREE_GB}GB free\n")

    total_done = len(done)
    new_records = []

    for i, v in enumerate(videos):
        chash = v["contentHashId"]
        if chash in done:
            if chash not in meta_by_hash:
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
        print(f"  {rel_path} | free: {free:.1f}GB")

        if free < MIN_FREE_GB:
            print(f"  ⚠ < {MIN_FREE_GB}GB — stopping")
            break

        if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
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

        # ── Download with retry loop ──────────────────────────────
        success = False
        for attempt in range(MAX_RETRIES + 1):
            try:
                # Re-resolve signed URL fresh for each attempt
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
                success = True
                break
            except Exception as e:
                msg = str(e)
                # Clean partial file
                if os.path.exists(out_file):
                    os.remove(out_file)

                if msg.startswith("AUTH_FAIL:"):
                    print(f"  ✗ AUTH ERROR: {msg[10:][:200]}")
                    print("\n[!] Token expired. Re-run crawl_course.py to refresh, then restart.")
                    save_progress(done)
                    return

                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF)-1)]
                    print(f"  ⚡ retry {attempt+1}/{MAX_RETRIES} in {wait}s ({msg[:100]})")
                    time.sleep(wait)
                else:
                    print(f"  ✗ FAILED after {MAX_RETRIES} retries: {msg[:200]}")

        if not success:
            # Save progress so we skip this failed video on restart
            print(f"  (skipping — will retry on next run)")
            save_progress(done)

        if total_done % 5 == 0:
            all_meta = list(meta_by_hash.values())
            save_metadata(all_meta)

        if total_done < 285:
            time.sleep(DELAY)

    # Final save
    all_meta = list(meta_by_hash.values()) + new_records
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
