#!/usr/bin/env python3
"""Check ABM download progress — videos done, disk usage, recent downloads."""
import json, os, shutil

PROGRESS = os.path.expanduser("~/development/classplus-dl/abm_progress.json")
META = os.path.expanduser("~/development/classplus-dl/abm_metadata.json")
OUTPUT = os.path.expanduser("~/development/classplus-dl/videos/ABM JUNE 2026")

total = 285

# Progress
if os.path.exists(PROGRESS):
    p = json.load(open(PROGRESS))
    done = len(p["done"])
else:
    done = 0

# Disk
free = shutil.disk_usage(OUTPUT).free / (1024**3)

# Metadata
if os.path.exists(META):
    m = json.load(open(META))
    total_bytes = sum(x["file_size_bytes"] for x in m)
    print(f"Videos:  {done}/{total} done")
    print(f"Data:    {total_bytes/(1024**3):.1f} GB downloaded")
    print(f"Avg:     {total_bytes/done/(1024**2):.0f} MB/video" if done else "")
    print(f"Disk:    {free:.1f} GB free")
    print()
    print("Last 5:")
    for x in m[-5:]:
        print(f"  {x['name'][:100]}")
        print(f"  → {x['file_size_bytes']/(1024**2):.0f}MB  sha256={x['sha256'][:16]}...")
else:
    print(f"Videos:  {done}/{total} done")
    print(f"Disk:    {free:.1f} GB free")
    print("(no metadata yet)")
