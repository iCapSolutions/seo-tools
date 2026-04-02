#!/usr/bin/env bash
# update_wp_post_tags.sh
# Update the categories and/or tags of a WordPress post via the REST API.
#
# Usage:
#   ./scripts/update_wp_post_tags.sh <post-id> <categories> <tags>
#
#   post-id      Numeric WordPress post ID
#   categories   Comma-separated category IDs  (e.g. "31"  or "31,4")
#   tags         Comma-separated tag IDs        (e.g. "32,34,40,41,42,43")
#
# Example:
#   ./scripts/update_wp_post_tags.sh 1477 31 "32,34,40,41,42,43"

if [[ -z "${WP_SITE_URL:-}" || -z "${WP_USERNAME:-}" || -z "${WP_APP_PASSWORD:-}" ]]; then
  echo "Missing required env vars: WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD"
  exit 1
fi

POST_ID="${1:-}"
CATEGORIES_CSV="${2:-}"
TAGS_CSV="${3:-}"

if [[ -z "$POST_ID" ]]; then
  echo "Usage: $0 <post-id> <categories-csv> <tags-csv>"
  exit 1
fi

AUTH_B64="$(printf "%s:%s" "$WP_USERNAME" "$WP_APP_PASSWORD" | base64)"
UA="Mozilla/5.0 Chrome/120.0"

# Build JSON arrays from CSV values
PAYLOAD="$(python3 - <<PYEOF
import json

def csv_to_int_list(s):
    return [int(x.strip()) for x in s.split(',') if x.strip()]

payload = {}
cats = csv_to_int_list("${CATEGORIES_CSV}")
tags = csv_to_int_list("${TAGS_CSV}")
if cats:
    payload['categories'] = cats
if tags:
    payload['tags'] = tags

print(json.dumps(payload))
PYEOF
)"

echo "Updating post ${POST_ID} taxonomy..."
echo "  Payload: ${PAYLOAD}"
echo

TMPFILE="$(mktemp)"
curl -sS -X POST \
  -H "Authorization: Basic ${AUTH_B64}" \
  -H "Content-Type: application/json" \
  -H "User-Agent: ${UA}" \
  -d "${PAYLOAD}" \
  "${WP_SITE_URL}/wp-json/wp/v2/posts/${POST_ID}" > "${TMPFILE}"

python3 - "${TMPFILE}" <<'PYEOF'
import json, sys

with open(sys.argv[1]) as f:
    raw = f.read()

try:
    d = json.loads(raw)
except Exception as e:
    print("Failed to parse response:", e)
    print(raw[:500])
    sys.exit(1)

if 'code' in d:
    print("Error:", d.get('code'), d.get('message', ''))
    sys.exit(1)

cats = d.get('categories', [])
tags = d.get('tags', [])
print(f"  Post ID:    {d.get('id')}")
print(f"  Title:      {d.get('title', {}).get('rendered', '')}")
print(f"  Status:     {d.get('status')}")
print(f"  Categories: {cats}")
print(f"  Tags:       {tags}")
print()
print("Done.")
PYEOF

rm -f "${TMPFILE}"
