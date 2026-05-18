# Classplus Course 696969 — Bulk Download Research

## Session History (Firefox)

Last Classplus session: **May 12–13, 2026**

| Time | URL |
|---|---|
| 22:55:03 | `web.classplusapp.com/login?orgCode=svkjm` |
| 22:55:40 | `/store/home` → `/store/home?tabCategoryId=2` |
| 22:55:47 | `/store/course/696969?section=overview` |
| 01:24:54 | `/store/course/696969?section=overview` (revisited) |
| 01:34:40 | `/store/course/696969?section=overview` (revisited) |
| 01:35:20 | `api.classplusapp.com/cams/uploader/video/jw-signed-url?contentId=...` |

**Downloaded**: `CH10_PART_I_Fundamentals_of_HRM.mp4` (281.5 MB) — single video from the course.

---

## Course Structure

**Course ID**: `696969`  
**Org Code**: `svkjm`

### Top-Level Folders

| Folder ID | Name | Videos | Files | Tests |
|---|---|---|---|---|
| `47128853` | ABM JUNE 2026 | 285 | 217 | 43 |
| ? | BFM JUNE 2026 | 432 | 385 | 87 |
| ? | ABFM JUNE 2026 | 159 | 78 | 89 |
| ? | BRBL JUNE 2026 | 125 | 64 | 121 |
| **Total** | | **~1001** | | |

### Folder Tree (partial, observed)

```
Course 696969 (root, folder_id=0)
├─ 47128853  ABM JUNE 2026
│  └─ 47367354  MODULE WISE LECTURES (A+B+C+D)
│     └─ 47367356  CH 1 PART I [Definition of Statistics, Importance & Limitations & Data Collection]
│     └─ … (more chapters)
│  └─ … (more subfolders)
├─ ?  BFM JUNE 2026
├─ ?  ABFM JUNE 2026
└─ ?  BRBL JUNE 2026
```

### URL Pattern

```
https://web.classplusapp.com/store/course/{course_id}/{folder_id}?section=content&pf={encoded_path}
```

### `pf` Parameter

Base64-encoded JSON (URL-safe, no padding). Encodes the folder ancestry chain:

```json
{
  "47128853": {"pfi": 0, "pfn": "", "cci": 696969, "pci": null},
  "47367354": {"pfi": 47128853, "pfn": "", "cci": 696969, "pci": null},
  "47367356": {"pfi": 47367354, "pfn": "", "cci": 696969, "pci": null}
}
```

**Fields**:
- `pfi` — parent folder ID (0 = course root)
- `pfn` — parent folder name (usually empty in observed URLs)
- `cci` — course ID
- `pci` — parent course ID (null for root course)

Each nesting level in the tree adds one entry. The last entry's key is the current folder.

---

## Known API Endpoints

### Signed Video URL (verified working)
```
GET https://api.classplusapp.com/cams/uploader/video/jw-signed-url?contentId=<encrypted>
Headers:
  x-access-token: <JWT>
  region: IN
  Origin: https://web.classplusapp.com
  Referer: https://web.classplusapp.com/
Response: {"url": "<signed-m3u8-url>", "success": true}
```

### Additional Endpoints (observed via Playwright interception)
```
GET  /analytics-api/v1/session/token        → {status, data, message}
GET  /v3/countryData/ip                     → {status, data, message}
GET  /v2/orgs/svkjm                         → {status, data, message}
GET  /v2/org/settings/login/                → {status, data, message}
```

### Missing: Folder Content Listing API
This is the **critical missing endpoint**. The web app calls it when navigating into a folder to fetch the list of subfolders, videos, and files. It was **not captured** during testing because the browser session wasn't authenticated (no login performed).

#### Candidate Patterns to Probe
- `GET /cams/uploader/video/batch-content?courseId={id}&folderId={id}`
- `GET /v2/org/course/{course_id}/folder/{folder_id}/content`
- `GET /v2/course/{course_id}/content?folderId={id}`
- `GET /cams/uploader/video/folder-content?folderId={id}`

---

## Automation Approach

### Playwright + Chromium (`crawl_course.py`)

**Status**: Working, but requires manual OTP login.

**Setup**:
```bash
pip install playwright && playwright install chromium
python3 crawl_course.py 696969
```

**Flow**:
1. Launches Chromium with `page.on("response")` interceptor
2. Navigates to course content page
3. Captures all API calls to `classplusapp.com`
4. Saves responses to `/tmp/classplus_api_*.json`
5. Waits for signal (`touch /tmp/classplus_done`) or browser close

**Known issues**:
- `page.route("**/*", ...)` blocks page load — use `page.on("response", ...)` only
- Requires user to log in manually (OTP to phone)
- stdin unavailable in tool context — use signal file instead of `input()`

### Selenium + Geckodriver (abandoned)
- Works with system Firefox profile
- But JS injection lost across page navigations
- No native network interception (requires BiDi protocol, Firefox 129+)

### Direct API Approach (preferred — once token + folder API are known)
```python
import requests
TOKEN = "<JWT>"
API_BASE = "https://api.classplusapp.com"
resp = requests.get(f"{API_BASE}/cams/uploader/video/???",
                     headers={"x-access-token": TOKEN, "region": "IN"})
```

---

## Next Steps (when OTP access available)

1. **Log in** to classplusapp.com in real Firefox
2. **Run `classplus-grab.js`** in console → `cpGrab.token()` to get JWT
3. **Open DevTools Network tab**, filter `classplusapp.com`
4. **Click into ABM JUNE 2026 folder** → observe the XHR/fetch call that loads folder contents
5. **Share**: the folder-listing API URL + JWT token
6. **Run crawl script**: iterate all folders via API, resolve every video contentId → download with `classplus-dl.sh`

---

## Estimated Download Size

~1001 videos × ~200–500 MB each ≈ **200–500 GB** total.
Verify disk space before bulk download.
