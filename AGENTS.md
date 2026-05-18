# Repository Guidelines

## Project Overview

`classplus-dl` extracts video content from **Classplus** (classplusapp.com) for offline viewing. Two tools work in tandem: a browser console script to capture authentication tokens and content IDs, and a shell script to download HLS video streams.

Course 696969 (org `svkjm`) was fully crawled: **1001 videos** across 4 subjects (ABM 285, BFM 432, ABFM 159, BRBL 125) totaling ~167 hours of content.

## Architecture & Data Flow

```
┌─ Phase 1: Auth Discovery ──────────────────────────────────────────┐
│                                                                     │
│  crawl_course.py (Playwright Chromium)                              │
│    │ Launches browser with persistent profile                       │
│    │ page.on("response") → intercepts all classplusapp.com calls    │
│    │ Extracts JWT token from x-access-token header + localStorage   │
│    │ Saves to /tmp/classplus_manifest.json                          │
│    │ Also saves API response bodies to /tmp/classplus_api_*.json    │
│                                                                     │
├─ Phase 2: Course Crawling ─────────────────────────────────────────┤
│                                                                     │
│  crawl_all.py (requests)                                            │
│    │ Reads token from /tmp/classplus_manifest.json                  │
│    │ Recursive DFS on GET /v2/course/content/get?folderId=N         │
│    │   contentType=1 → subfolder (recurse)                          │
│    │   contentType=2 → video (record name, contentHashId, duration) │
│    │ Saves 1001 videos to /tmp/classplus_video_manifest.json        │
│                                                                     │
├─ Phase 3: Download ────────────────────────────────────────────────┤
│                                                                     │
│  download_abm.py / bulk_download.py (requests + ffmpeg)             │
│    │ For each contentHashId:                                        │
│    │   GET /cams/uploader/video/jw-signed-url?contentId=<hash>      │
│    │   → signed m3u8 URL                                            │
│    │   → ffmpeg -i <signed_url> -c copy -bsf:a aac_adtstoasc .mp4  │
│    │ Single-threaded, 3s delay, resumable via progress JSON         │
│    │ Output: ~/videos/{Subject}/{Module}/.../{Chapter}.mp4          │
│    │ Metadata: JSON + CSV with SHA-256 checksums                    │
│                                                                     │
├─ Manual Fallback ──────────────────────────────────────────────────┤
│                                                                     │
│  classplus-grab.js (browser console IIFE)                           │
│    │ cpGrab.token() → JWT from localStorage/cookies/React fiber     │
│    │ cpGrab.encId()  → encrypted contentId from fetch interception  │
│    │                                                            │
│  classplus-dl.sh (bash)                                             │
│    │ ./classplus-dl.sh <contentId> [output]                         │
│    │ CLASSPLUS_TOKEN env var → curl API → ffmpeg download           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Files

| File | Role |
|---|---|
| `classplus-grab.js` | Browser console IIFE — intercepts fetch, searches storage/React fiber, exposes `cpGrab.*` API |
| `classplus-dl.sh` | Bash script — single-video download via curl + ffmpeg |
| `crawl_course.py` | Playwright Chromium — launches browser, intercepts API calls, extracts token + endpoints |
| `crawl_all.py` | Recursive API crawler — walks 4-subject folder tree, builds 1001-video manifest |
| `bulk_download.py` | Generic bulk downloader — manifest → signed URLs → ffmpeg → .mp4, resumable |
| `download_abm.py` | Subject-specific downloader — ABM only, checksums, metadata CSV/JSON, disk guard |
| `check_progress.py` | Status reporter — reads progress JSON, prints done/total, disk usage, recent files |
| `RESEARCH.md` | Full research notes — session history, course tree, API endpoints, automation approach |

## API Endpoints

### Video Signing (used by download scripts)
```
GET https://api.classplusapp.com/cams/uploader/video/jw-signed-url?contentId=<encrypted>
Headers: x-access-token, region: IN, Origin, Referer
Response: {"url": "<signed-m3u8-url>", "success": true}
```

### Folder Content Listing (used by crawl_all.py)
```
GET https://api.classplusapp.com/v2/course/content/get?courseId=696969&folderId=<id>
Headers: x-access-token, region: IN, Origin, Referer
Response: {"status": "success", "data": {"courseContent": [
  {"contentType": 1, "id": ..., "name": "...", "videoCount": ...},  // folder
  {"contentType": 2, "id": ..., "name": "...", "contentHashId": "...", "duration": "..."}  // video
]}}
```
- `folderId=0` = course root
- `contentType=1` = subfolder (recurse into its `id`)
- `contentType=2` = video (`contentHashId` is the encrypted contentId)

### Additional (observed, not used)
```
GET  /v2/course/696969              — course metadata
GET  /v2/orgs/{orgCode}             — org info
GET  /v2/org/details                — org details
GET  /analytics-api/v1/session/token — analytics
GET  /v3/countryData/ip             — geo lookup
```

## Development Commands

```bash
# Syntax-check the JS
node --check classplus-grab.js

# Lint the shell script
shellcheck classplus-dl.sh

# Single video download (manual)
CLASSPLUS_TOKEN='<jwt>' ./classplus-dl.sh <contentHashId> [output-name]

# API discovery (launches browser — log in, click folders)
python3 crawl_course.py 696969

# Recursive course crawl (needs token from crawl_course.py first)
python3 crawl_all.py

# Bulk download — ABM only, with checksums + metadata
python3 download_abm.py

# Bulk download — all 1001 videos
python3 bulk_download.py

# Check ABM progress
python3 check_progress.py

# Run in tmux so downloads survive terminal close
tmux new-session -d -s classplus -c . "python3 download_abm.py 2>&1 | tee /tmp/abm_download.log"
tmux attach -t classplus
```

## Runtime / Tooling Preferences

- **Shell**: `bash` 4+ with `set -euo pipefail` (strict mode)
- **Python**: 3.10+ with `requests`, `playwright` (`pip install playwright && playwright install chromium`)
- **Browser**: Chromium for Playwright (bundled); Firefox for manual use
- **Dependencies**: `ffmpeg`, `curl`, `python3`, `tmux` (optional, for persistent downloads)
- **OS**: macOS primary (`brew install ffmpeg geckodriver`); Linux compatible
- No `jq` — Python3 handles all JSON in shell scripts

## Code Conventions & Common Patterns

### Shell (`classplus-dl.sh`)
- **Strict mode**: `set -euo pipefail` — fail on any error, unset variable, pipe failure
- **Error handling**: `die()` helper prints `ERROR:` in red to stderr and exits
- **ANSI colors**: `RED`, `GREEN`, `YELLOW`, `NC` vars at top
- **Whitespace stripping**: `${VAR//[$'\t\r\n ']/}` handles copy-paste artifacts
- **API calls**: `curl -s --max-time 15` with explicit `Origin` and `Referer` headers
- **JSON parsing**: Inline `python3 -c` one-liners (import json, load stdin, print field)
- **ffmpeg**: `-c copy -bsf:a aac_adtstoasc` — stream copy with AAC ADTS→ASC conversion for MP4 compatibility
- **No jq, no sed/awk JSON hacks, no temp files** — everything is in-memory pipe-based

### JavaScript (`classplus-grab.js`)
- **Format**: IIFE with `"use strict"` — direct paste into browser console
- **Token discovery**: Cascading fallback: `localStorage` → `sessionStorage` → `cookies` → React fiber walk (depth≤15, finds `memoizedState.token`)
- **Fetch interception**: Monkey-patches `window.fetch`, captures `x-access-token` from outgoing headers and `contentId` from `jw-signed-url` query params
- **Public API**: `window.cpGrab.token()`, `.encId()`, `.all()`, `.help()` — styled `console.log` with `%c` directives

### Python (crawlers/downloaders)
- **Auth pass-through**: All scripts read token from `/tmp/classplus_manifest.json` (single source of truth)
- **Progress tracking**: JSON files with contentHashId-based sets — crash-resumable
- **Incremental saves**: Progress + metadata flushed after each download (and every 5 downloads for metadata)
- **Disk guard**: `shutil.disk_usage` check before each download, stops if < 5GB free
- **Single-threaded**: `requests` + `time.sleep(3)` — no asyncio, no threading, no connection pools
- **Headers pattern**: Every API call includes `x-access-token`, `region: IN`, `Origin`, `Referer`
- **Sanitization**: Filenames stripped of `<>:"/\|?*`, truncated to 180–200 chars
- **Resumability**: File-existence + size>0 check before downloading; progress JSON updated on success

## Testing & QA

No automated tests. Manual verification:

```bash
# Verify manifest integrity
python3 -c "
import json
v = json.load(open('/tmp/classplus_video_manifest.json'))
print(f'Videos: {v[\"total_videos\"]}')
print(f'Empty hashes: {sum(1 for x in v[\"videos\"] if not x[\"contentHashId\"])}')
"

# Verify a single download works
python3 -c "
import json, requests
videos = json.load(open('/tmp/classplus_video_manifest.json'))['videos']
token = json.load(open('/tmp/classplus_manifest.json'))['token']
v = videos[0]
r = requests.get('https://api.classplusapp.com/cams/uploader/video/jw-signed-url',
    params={'contentId': v['contentHashId']},
    headers={'x-access-token': token, 'region': 'IN'})
print('OK' if r.json().get('success') else 'FAIL')
"

# Check download integrity
python3 check_progress.py
```

## Output File Inventory

| Path | Producer | Schema |
|---|---|---|
| `/tmp/classplus_manifest.json` | `crawl_course.py` | `{token, endpoints[], folder_api_candidate, responses[]}` |
| `/tmp/classplus_video_manifest.json` | `crawl_all.py` | `{course_id, total_videos, videos[{name, folder_path, contentHashId, duration, id}]}` |
| `/tmp/classplus_abm_manifest.json` | filtered from above | Same schema, ABM only (285 videos) |
| `abm_progress.json` | `download_abm.py` | `{"done": ["contentHashId", ...]}` |
| `abm_metadata.json` | `download_abm.py` | `[{name, folder, duration, contentHashId, file_path, file_size_bytes, sha256, downloaded_at}]` |
| `abm_metadata.csv` | `download_abm.py` | Same fields as CSV |
| `videos/ABM JUNE 2026/.../` | `download_abm.py` | `.mp4` files preserving folder hierarchy |

## Resume Point (ongoing download)

ABM download running in tmux session `classplus`. To interact:
```bash
tmux attach -t classplus    # watch live
python3 check_progress.py   # quick status
```

If token expires mid-download: log in to classplus in browser, run `cpGrab.token()`, update the `token` field in `/tmp/classplus_manifest.json`, then re-run the download script — it resumes from where it stopped.
