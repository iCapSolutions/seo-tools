#!/usr/bin/env bash
# pick_wp_image.sh
# Fetch 3 image options from Unsplash and upload them to WordPress.
# Preview the three URLs in WP Admin > Media, then pass your chosen
# media ID to update_wp_page.sh as arg 7.
#
# Usage:
#   ./scripts/pick_wp_image.sh "keywords" [width] [height]
#   ./scripts/pick_wp_image.sh "keywords" [width] [height] "alt B keywords" "alt C keywords"
#
# Examples:
#   ./scripts/pick_wp_image.sh "cloud devops technology" 1600 450
#   ./scripts/pick_wp_image.sh "git code terminal" 1600 450 "command line dark unix" "programming editor screen"
#
# After running, pick the best image and apply it:
#   ./scripts/update_wp_page.sh <page-id> <html-file> publish "" "" "" <media-id>
#
# Requires: UNSPLASH_ACCESS_KEY env var for best results.
#           Falls back to loremflickr (limited variety) if not set.

set -uo pipefail

if [[ -z "${WP_SITE_URL:-}" || -z "${WP_USERNAME:-}" || -z "${WP_APP_PASSWORD:-}" ]]; then
  echo "Missing required env vars: WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD"
  exit 1
fi

KEYWORDS="${1:-technology}"
WIDTH="${2:-1600}"
HEIGHT="${3:-900}"
KW_B="${4:-$KEYWORDS}"
KW_C="${5:-$KEYWORDS}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  Fetching 3 image options  (${WIDTH}x${HEIGHT})"
echo ""

for opt in A B C; do
  case $opt in
    A) KW="$KEYWORDS" ;;
    B) KW="$KW_B" ;;
    C) KW="$KW_C" ;;
  esac
  echo "─── Option $opt ── \"$KW\" ─────────────────────────────"
  "${SCRIPT_DIR}/add_wp_image.sh" "$KW" "$WIDTH" "$HEIGHT"
  echo ""
  [[ "$opt" != "C" ]] && sleep 1
done

echo "  ✓ Done. Preview images in WP Admin → Media Library."
echo ""
echo "  Apply your chosen image:"
echo "    ./scripts/update_wp_page.sh <page-id> <html-file> publish \"\" \"\" \"\" <media-id>"
echo ""
