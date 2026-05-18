# classplus-video-download-suite

Tools to extract and bulk-download video content from **Classplus** (classplusapp.com) for **personal offline viewing** of purchased courses.

## What it does

- Captures JWT auth tokens from browser session
- Crawls entire course folder trees to enumerate every video
- Downloads all videos via signed HLS URLs → `.mp4` (stream copy, no transcode)
- Tracks progress with resume support, SHA-256 checksums, and metadata CSV/JSON

## Files

| File | Purpose |
|---|---|
| `classplus-grab.js` | Paste into browser console — captures JWT token + encrypted contentId |
| `classplus-dl.sh` | Single-video downloader (curl + ffmpeg) |
| `crawl_course.py` | Playwright Chromium — API discovery, extracts token + endpoints |
| `crawl_all.py` | Recursive folder crawler — builds video manifest from API |
| `download_abm.py` | Bulk downloader with checksums, metadata, disk guard, resume |
| `bulk_download.py` | Generic bulk downloader for all subjects |
| `check_progress.py` | Prints download progress and disk usage |
| `AGENTS.md` | Full architecture and development guide |
| `RESEARCH.md` | Course structure notes and API reverse-engineering details |

## Quick Start

### 1. Install dependencies

```bash
# macOS
brew install ffmpeg tmux
pip install requests playwright
playwright install chromium
```

### 2. Capture auth token (one-time)

```bash
python3 crawl_course.py 696969
```
Launches Chromium. Log in to classplusapp.com, navigate the course. Close browser or `touch /tmp/classplus_done`.

### 3. Crawl the course

```bash
python3 crawl_all.py
```
Outputs 1001 videos to `/tmp/classplus_video_manifest.json`.

### 4. Download

```bash
# Single subject (ABM — 285 videos, ~150 GB)
tmux new-session -d -s dl "python3 download_abm.py 2>&1 | tee /tmp/abm_download.log"

# Or everything (1001 videos, ~500 GB)
tmux new-session -d -s dl "python3 bulk_download.py 2>&1 | tee /tmp/download.log"

# Check progress
python3 check_progress.py
tmux attach -t dl
```

### Manual single-video download

```bash
export CLASSPLUS_TOKEN='your-jwt-token'
./classplus-dl.sh <encrypted-content-id> output-name
```

## Output

```
videos/
└── ABM JUNE 2026/
    ├── MODULE WISE LECTURES (A+B+C+D)/
    │   ├── MODULE A: STATISTICS/
    │   │   ├── CH 1 PART I Statistics.mp4
    │   │   └── ...
    │   └── MODULE B: HUMAN RESOURCE MANAGEMENT/
    │       └── ...
    ├── LIVE CLASSES/
    │   └── ...
    └── CASE STUDY & RECALLED QUESTIONS/
        └── ...
```

Each download produces:
- `*_progress.json` — resume state
- `*_metadata.json` + `*_metadata.csv` — SHA-256 checksums, file sizes, timestamps

## How it works

```
Browser login  →  crawl_course.py captures JWT + API endpoints
                              ↓
              crawl_all.py recursively calls folder-listing API
                              ↓
            /tmp/classplus_video_manifest.json (1001 videos)
                              ↓
          download_abm.py resolves each contentHashId
              → GET /cams/uploader/video/jw-signed-url?contentId=<hash>
              → signed m3u8 URL
              → ffmpeg -c copy → .mp4
```

## Disclaimer

This tool is intended for **personal offline viewing of legally purchased course content**. It does not:
- Circumvent DRM (videos have `drmProtected: 0`)
- Bypass paywalls (requires valid purchased account)
- Enable redistribution of copyrighted material

Using this tool may violate Classplus's Terms of Service. The author assumes no liability for account suspensions or other consequences. Use at your own risk.

## License

Mozilla Public License 2.0 — see [LICENSE](LICENSE)
