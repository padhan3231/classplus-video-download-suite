#!/usr/bin/env bash
# classplus-dl — download Classplus videos for offline viewing
# Usage:
#   export CLASSPLUS_TOKEN='eyJh...'
#   ./classplus-dl.sh <encrypted-content-id> [output-name]
#
# Requires: ffmpeg, curl, python3
# Get the encrypted contentId from your browser's DevTools Network tab:
#   Filter: jw-signed-url → copy the contentId=... value from the URL
# Or use classplus-grab.js (paste in browser console, click a video).

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

die() { echo -e "${RED}ERROR:${NC} $*" >&2; exit 1; }

# ── Check dependencies ──────────────────────────────────────────────
command -v ffmpeg >/dev/null 2>&1 || die "ffmpeg required: brew install ffmpeg"
command -v curl  >/dev/null 2>&1 || die "curl required"
command -v python3 >/dev/null 2>&1 || die "python3 required"

# ── Args ────────────────────────────────────────────────────────────
ENC_CONTENT_ID="${1:-}"
OUTPUT_NAME="${2:-}"

if [[ -z "$ENC_CONTENT_ID" ]]; then
    echo "Usage: $0 <encrypted-content-id> [output-name]"
    echo ""
    echo "  encrypted-content-id: the encoded contentId value from the"
    echo "                        jw-signed-url API call's query string."
    echo "                        Get it from DevTools → Network → filter 'jw-signed-url'"
    echo "                        Or use classplus-grab.js bookmarklet."
    echo ""
    echo "  output-name:          optional output filename (default: auto-generated .mp4)"
    echo ""
    echo "Environment:"
    echo "  CLASSPLUS_TOKEN       JWT x-access-token from any API request header"
    exit 1
fi

# ── JWT Token ───────────────────────────────────────────────────────
TOKEN="${CLASSPLUS_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
    read -rsp "Paste x-access-token (JWT): " TOKEN
    echo ""
fi
[[ -z "$TOKEN" ]] && die "Token required"

# Strip whitespace from pasted values
TOKEN="${TOKEN//[$'\t\r\n ']/}"
ENC_CONTENT_ID="${ENC_CONTENT_ID//[$'\t\r\n ']/}"

# ── API call: get signed m3u8 URL ───────────────────────────────────
echo -e "${YELLOW}Fetching signed video URL...${NC}"

API_RESPONSE=$(curl -s --max-time 15 \
    "https://api.classplusapp.com/cams/uploader/video/jw-signed-url?contentId=${ENC_CONTENT_ID}" \
    -H "x-access-token: ${TOKEN}" \
    -H 'region: IN' \
    -H 'Origin: https://web.classplusapp.com' \
    -H 'Referer: https://web.classplusapp.com/')

SIGNED_URL=$(echo "$API_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('url',''))" 2>/dev/null)
SUCCESS=$(echo "$API_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('success',''))" 2>/dev/null)

if [[ "$SUCCESS" != "True" ]]; then
    echo -e "${RED}API error:${NC} $API_RESPONSE"
    die "Failed to get signed URL. Token may be expired or contentId invalid."
fi

[[ -z "$SIGNED_URL" ]] && die "No URL in response"

echo -e "${GREEN}✓ Signed URL obtained${NC}"

# ── Determine output filename ───────────────────────────────────────
if [[ -z "$OUTPUT_NAME" ]]; then
    OUTPUT_NAME="classplus-video-$(date +%s).mp4"
fi
[[ "$OUTPUT_NAME" != *.mp4 ]] && OUTPUT_NAME="${OUTPUT_NAME}.mp4"

# ── Download ────────────────────────────────────────────────────────
echo -e "${YELLOW}Downloading → ${OUTPUT_NAME}${NC}"
echo ""

ffmpeg -hide_banner -loglevel warning -stats \
    -i "$SIGNED_URL" \
    -c copy -bsf:a aac_adtstoasc \
    "$OUTPUT_NAME"

echo ""
echo -e "${GREEN}✓ Done: $(ls -lh "$OUTPUT_NAME" | awk '{print $5, $NF}')${NC}"
