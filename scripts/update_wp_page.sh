#!/usr/bin/env bash
# update_wp_page.sh
# Push revised HTML content back to a WordPress page.
# Saves as draft by default — safe for review before publishing.
#
# Usage:
#   ./scripts/update_wp_page.sh <page-id> <html-file> [status] [title] [meta-desc] [focus-kw] [featured-id] [slug]
#
#   status       draft (default) or publish
#   title        page title
#   meta-desc    Rank Math meta description — written via rankmath/v1/updateMeta
#   focus-kw     Rank Math focus keyword  — written via rankmath/v1/updateMeta
#   featured-id  WordPress media ID to set as featured image
#   slug         URL slug (e.g. 'about' → /about.html)

if [[ -z "${WP_SITE_URL:-}" || -z "${WP_USERNAME:-}" || -z "${WP_APP_PASSWORD:-}" ]]; then
  echo "Missing required env vars: WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD"
  exit 1
fi

PAGE_ID="${1:-}"
CONTENT_FILE="${2:-}"
STATUS="${3:-draft}"
TITLE="${4:-}"
META_DESC="${5:-}"
FOCUS_KW="${6:-}"
FEATURED_MEDIA="${7:-}"
SLUG="${8:-}"

if [[ -z "$PAGE_ID" || -z "$CONTENT_FILE" ]]; then
  echo "Usage: $0 <page-id> <html-file> [draft|publish] [title] [meta-desc] [focus-kw] [featured-id] [slug]"
  exit 1
fi

if [[ ! -f "$CONTENT_FILE" ]]; then
  echo "File not found: $CONTENT_FILE"
  exit 1
fi
AUTH_B64="$(printf "%s:%s" "$WP_USERNAME" "$WP_APP_PASSWORD" | base64)"
POST_TYPE="${POST_TYPE:-pages}"   # override with POST_TYPE=posts for blog posts
UA="Mozilla/5.0 Chrome/120.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_FILE="${REPO_ROOT}/docs/page-grooming-log.md"
GROOMED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Build and send the WordPress page update payload
PAYLOAD="$(python3 "${SCRIPT_DIR}/_wp_build_payload.py" \
  "$CONTENT_FILE" "$STATUS" "$TITLE" "$META_DESC" "$FOCUS_KW" \
  "$GROOMED_AT" "$FEATURED_MEDIA" "$SLUG")"

echo "Updating page ID ${PAGE_ID} (status: ${STATUS})..."
TMP_RESPONSE="$(mktemp)"
curl -sS -X POST \
  -H "Authorization: Basic ${AUTH_B64}" \
  -H "Content-Type: application/json" \
  -H "User-Agent: ${UA}" \
  -d "$PAYLOAD" \
  "${WP_SITE_URL}/wp-json/wp/v2/${POST_TYPE}/${PAGE_ID}" > "$TMP_RESPONSE"

# Extract fields via helper — avoids bash 3.2 nested-quote issues with python3 -c
PAGE_ID_OUT="$(python3 "${SCRIPT_DIR}/_wp_extract_fields.py" "$TMP_RESPONSE" id)"
TITLE_OUT="$(  python3 "${SCRIPT_DIR}/_wp_extract_fields.py" "$TMP_RESPONSE" title.rendered)"
STATUS_OUT="$( python3 "${SCRIPT_DIR}/_wp_extract_fields.py" "$TMP_RESPONSE" status)"
LINK_OUT="$(   python3 "${SCRIPT_DIR}/_wp_extract_fields.py" "$TMP_RESPONSE" link)"
rm -f "$TMP_RESPONSE"

echo
echo "  ID:     ${PAGE_ID_OUT}"
echo "  Title:  ${TITLE_OUT}"
echo "  Status: ${STATUS_OUT}"
echo "  Link:   ${LINK_OUT}"

# Push SEO meta to Rank Math via its own API
if [[ -n "$META_DESC" || -n "$FOCUS_KW" ]]; then
  TMP_RM="$(mktemp)"
  RM_PAYLOAD="$(python3 "${SCRIPT_DIR}/_wp_rankmath_payload.py" \
    "$META_DESC" "$FOCUS_KW" "$PAGE_ID_OUT")"
  curl -sS -X POST \
    -H "Authorization: Basic ${AUTH_B64}" \
    -H "Content-Type: application/json" \
    -H "User-Agent: ${UA}" \
    -d "$RM_PAYLOAD" \
    "${WP_SITE_URL}/wp-json/rankmath/v1/updateMeta" > "$TMP_RM"
  RM_SLUG="$(python3 "${SCRIPT_DIR}/_wp_extract_fields.py" "$TMP_RM" slug 2>/dev/null)"
  if [[ -n "$RM_SLUG" ]]; then RM_RESULT="ok"; else RM_RESULT="failed"; fi
  rm -f "$TMP_RM"
  echo "  Rank Math SEO: ${RM_RESULT}"
fi

echo

# Append to local grooming log
echo "| ${GROOMED_AT} | ${PAGE_ID_OUT} | ${TITLE_OUT} | ${STATUS_OUT} | [link](${LINK_OUT}) | Oz (Warp) |" >> "$LOG_FILE"
echo "  Logged to docs/page-grooming-log.md"
