#!/usr/bin/env bash

set -uo pipefail

if [[ -z "${WP_SITE_URL:-}" || -z "${WP_USERNAME:-}" || -z "${WP_APP_PASSWORD:-}" ]]; then
  echo "Missing required env vars: WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD"
  exit 1
fi

TITLE="${1:-iCapSolutions test post}"
CONTENT_HTML="${2:-<p>Test publish from scripts/manual_publish_wordpress.sh</p>}"

AUTH_B64="$(printf "%s:%s" "$WP_USERNAME" "$WP_APP_PASSWORD" | base64)"

curl -sS -X POST "${WP_SITE_URL}/wp-json/wp/v2/posts" \
  -H "Authorization: Basic ${AUTH_B64}" \
  -H "Content-Type: application/json" \
  -d "$(printf '{"title":"%s","content":"%s","status":"draft"}' "$TITLE" "$CONTENT_HTML")"
