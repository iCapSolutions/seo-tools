#!/usr/bin/env bash
# add_wp_image.sh
# Fetch an image by keyword from Unsplash and upload it to WordPress media.
# Prints the WordPress media ID on success — pass it as arg 7 to update_wp_page.sh.
#
# Usage:
#   ./scripts/add_wp_image.sh "cloud devops technology"
#   ./scripts/add_wp_image.sh "cloud devops technology" 1600 450   # custom dimensions (banner)
#
# Uses UNSPLASH_ACCESS_KEY if set (recommended).
# Falls back to loremflickr.com (free, no key, keyword-based CC photos).

set -uo pipefail

if [[ -z "${WP_SITE_URL:-}" || -z "${WP_USERNAME:-}" || -z "${WP_APP_PASSWORD:-}" ]]; then
  echo "Missing required env vars: WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD"
  exit 1
fi

KEYWORDS="${1:-technology}"
IMG_WIDTH="${2:-1600}"
IMG_HEIGHT="${3:-900}"
KEYWORDS_ENCODED="${KEYWORDS// /+}"
TMP_IMG="/tmp/wp-upload-$(date +%s).jpg"
TMP_META="/tmp/wp-upload-meta-$(date +%s).json"
FILENAME="$(echo "$KEYWORDS" | tr ' ' '-' | tr '[:upper:]' '[:lower:]')-$(date +%s).jpg"

AUTH_B64="$(printf "%s:%s" "$WP_USERNAME" "$WP_APP_PASSWORD" | base64)"
UA="Mozilla/5.0 Chrome/120.0"

# --- Fetch image ---
if [[ -n "${UNSPLASH_ACCESS_KEY:-}" ]]; then
  echo "Fetching from Unsplash API (keywords: ${KEYWORDS})..." >&2
  IMG_URL="$(curl -sS \
    "https://api.unsplash.com/photos/random?query=${KEYWORDS_ENCODED}&orientation=landscape&client_id=${UNSPLASH_ACCESS_KEY}" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['urls']['regular'])")"
else
  # loremflickr.com: free, no auth, keyword-based CC photos
  FLICKR_KEYWORDS="$(echo "$KEYWORDS" | tr ' ' ',')"
  SEED="$(date +%s | tail -c 6)"
  echo "UNSPLASH_ACCESS_KEY not set — using loremflickr.com (keywords: ${FLICKR_KEYWORDS}, seed: ${SEED})..." >&2
  IMG_URL="https://loremflickr.com/${IMG_WIDTH}/${IMG_HEIGHT}/${FLICKR_KEYWORDS}?lock=${SEED}"
fi

echo "Downloading image..." >&2
HTTP_CODE="$(curl -sS -L -o "$TMP_IMG" -w "%{http_code}" "$IMG_URL")"
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "Error: image download failed (HTTP ${HTTP_CODE})" >&2
  exit 1
fi

FILE_SIZE="$(wc -c < "$TMP_IMG" | tr -d ' ')"
echo "Downloaded ${FILE_SIZE} bytes → ${TMP_IMG}" >&2

# --- Upload to WordPress media ---
echo "Uploading to WordPress media library..." >&2
curl -sS -X POST \
  -H "Authorization: Basic ${AUTH_B64}" \
  -H "User-Agent: ${UA}" \
  -H "Content-Disposition: attachment; filename=\"${FILENAME}\"" \
  -H "Content-Type: image/jpeg" \
  --data-binary "@${TMP_IMG}" \
  "${WP_SITE_URL}/wp-json/wp/v2/media" \
  > "$TMP_META"

# Parse and print media ID
python3 -c "
import json, sys
with open('${TMP_META}') as f:
    d = json.load(f)
if 'id' not in d:
    print('Upload failed:', d.get('message', 'unknown error'), file=sys.stderr)
    sys.exit(1)
print()
print('  Media ID:  ' + str(d['id']))
print('  URL:       ' + d.get('source_url', ''))
print('  File:      ' + d.get('slug', ''))
print()
print(d['id'])
"

rm -f "$TMP_IMG" "$TMP_META"
