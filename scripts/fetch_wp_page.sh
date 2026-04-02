#!/usr/bin/env bash
# fetch_wp_page.sh
# List all pages (or posts) or fetch a single one by ID or slug.
#
# Usage:
#   ./scripts/fetch_wp_page.sh                 → list all pages (id, slug, title, status)
#   ./scripts/fetch_wp_page.sh <id>            → fetch page by numeric ID
#   ./scripts/fetch_wp_page.sh <slug>          → fetch page by slug
#
#   POST_TYPE=posts ./scripts/fetch_wp_page.sh          → list all posts
#   POST_TYPE=posts ./scripts/fetch_wp_page.sh <id>     → fetch post by ID

set -uo pipefail

if [[ -z "${WP_SITE_URL:-}" || -z "${WP_USERNAME:-}" || -z "${WP_APP_PASSWORD:-}" ]]; then
  echo "Missing required env vars: WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD"
  exit 1
fi

AUTH_B64="$(printf "%s:%s" "$WP_USERNAME" "$WP_APP_PASSWORD" | base64)"
POST_TYPE="${POST_TYPE:-pages}"   # override with POST_TYPE=posts for blog posts
UA="Mozilla/5.0 Chrome/120.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QUERY="${1:-}"

if [[ -z "$QUERY" ]]; then
  # List all pages/posts as a clean table
  echo "Fetching ${POST_TYPE} list..." >&2
  curl -sS \
    -H "Authorization: Basic ${AUTH_B64}" \
    -H "User-Agent: ${UA}" \
    "${WP_SITE_URL}/wp-json/wp/v2/${POST_TYPE}?per_page=100&_fields=id,slug,title,status" \
    | python3 -c "
import json, sys
pages = json.load(sys.stdin)
print(f\"{'ID':<8} {'STATUS':<12} {'SLUG':<55} TITLE\")
print('-' * 120)
for p in pages:
    pid    = str(p.get('id', ''))
    status = p.get('status', '')
    slug   = p.get('slug', '')
    title  = p.get('title', {}).get('rendered', '')
    print(f\"{pid:<8} {status:<12} {slug:<55} {title}\")
"

elif [[ "$QUERY" =~ ^[0-9]+$ ]]; then
  # Fetch full page/post by numeric ID
  echo "Fetching ${POST_TYPE} ID: ${QUERY}..." >&2
  curl -sS \
    -H "Authorization: Basic ${AUTH_B64}" \
    -H "User-Agent: ${UA}" \
    "${WP_SITE_URL}/wp-json/wp/v2/${POST_TYPE}/${QUERY}" \
    | python3 "${SCRIPT_DIR}/_wp_page_summary.py"

else
  # Fetch full page/post by slug
  echo "Fetching ${POST_TYPE} slug: ${QUERY}..." >&2
  curl -sS \
    -H "Authorization: Basic ${AUTH_B64}" \
    -H "User-Agent: ${UA}" \
    "${WP_SITE_URL}/wp-json/wp/v2/${POST_TYPE}?slug=${QUERY}" \
    | python3 "${SCRIPT_DIR}/_wp_page_summary.py"
fi
