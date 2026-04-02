#!/usr/bin/env bash
# manage_wp_taxonomy.sh
# Create, delete, or list WordPress tags and categories via the REST API.
#
# Usage:
#   ./scripts/manage_wp_taxonomy.sh list   [tags|categories]
#   ./scripts/manage_wp_taxonomy.sh create [tags|categories] <name> [slug]
#   ./scripts/manage_wp_taxonomy.sh delete [tags|categories] <id>
#
# Examples:
#   ./scripts/manage_wp_taxonomy.sh list tags
#   ./scripts/manage_wp_taxonomy.sh list categories
#   ./scripts/manage_wp_taxonomy.sh create tags "Enterprise AI" "enterprise-ai"
#   ./scripts/manage_wp_taxonomy.sh create categories "Cloud Strategy" "cloud-strategy"
#   ./scripts/manage_wp_taxonomy.sh delete tags 32
#   ./scripts/manage_wp_taxonomy.sh delete categories 4

if [[ -z "${WP_SITE_URL:-}" || -z "${WP_USERNAME:-}" || -z "${WP_APP_PASSWORD:-}" ]]; then
  echo "Missing required env vars: WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD"
  exit 1
fi

ACTION="${1:-}"
TYPE="${2:-}"

if [[ -z "$ACTION" || -z "$TYPE" ]]; then
  echo "Usage: $0 <list|create|delete> <tags|categories> [args...]"
  exit 1
fi

if [[ "$TYPE" != "tags" && "$TYPE" != "categories" ]]; then
  echo "Type must be 'tags' or 'categories'"
  exit 1
fi

AUTH_B64="$(printf "%s:%s" "$WP_USERNAME" "$WP_APP_PASSWORD" | base64)"
UA="Mozilla/5.0 Chrome/120.0"
ENDPOINT="${WP_SITE_URL}/wp-json/wp/v2/${TYPE}"
TMPFILE="$(mktemp)"

case "$ACTION" in

  list)
    curl -sS \
      -H "Authorization: Basic ${AUTH_B64}" \
      -H "User-Agent: ${UA}" \
      "${ENDPOINT}?per_page=100&_fields=id,name,slug,count" > "${TMPFILE}"

    python3 - "${TMPFILE}" "${TYPE}" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    items = json.load(f)
label = sys.argv[2].capitalize()
print(f"\n  {label} ({len(items)} total)\n")
print(f"  {'ID':<6} {'COUNT':<7} {'SLUG':<40} NAME")
print("  " + "-" * 70)
for item in sorted(items, key=lambda x: x['id']):
    print(f"  {item['id']:<6} {item.get('count', 0):<7} {item['slug']:<40} {item['name']}")
print()
PYEOF
    ;;

  create)
    NAME="${3:-}"
    SLUG="${4:-}"

    if [[ -z "$NAME" ]]; then
      echo "Usage: $0 create <tags|categories> <name> [slug]"
      exit 1
    fi

    PAYLOAD="$(python3 -c "
import json, sys
p = {'name': sys.argv[1]}
if sys.argv[2]:
    p['slug'] = sys.argv[2]
print(json.dumps(p))
" "$NAME" "$SLUG")"

    curl -sS -X POST \
      -H "Authorization: Basic ${AUTH_B64}" \
      -H "Content-Type: application/json" \
      -H "User-Agent: ${UA}" \
      -d "${PAYLOAD}" \
      "${ENDPOINT}" > "${TMPFILE}"

    python3 - "${TMPFILE}" "${TYPE}" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
if 'code' in d:
    print(f"Error: {d.get('code')} — {d.get('message', '')}")
    sys.exit(1)
label = sys.argv[2].rstrip('s').capitalize()
print(f"\n  {label} created:")
print(f"  ID:   {d.get('id')}")
print(f"  Name: {d.get('name')}")
print(f"  Slug: {d.get('slug')}")
print()
PYEOF
    ;;

  delete)
    ID="${3:-}"

    if [[ -z "$ID" ]]; then
      echo "Usage: $0 delete <tags|categories> <id>"
      exit 1
    fi

    curl -sS -X DELETE \
      -H "Authorization: Basic ${AUTH_B64}" \
      -H "User-Agent: ${UA}" \
      "${ENDPOINT}/${ID}?force=true" > "${TMPFILE}"

    python3 - "${TMPFILE}" "${TYPE}" "${ID}" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
if 'code' in d:
    print(f"Error: {d.get('code')} — {d.get('message', '')}")
    sys.exit(1)
label = sys.argv[2].rstrip('s').capitalize()
print(f"\n  {label} ID {sys.argv[3]} deleted.")
print(f"  Was: \"{d.get('previous', {}).get('name', '?')}\"")
print()
PYEOF
    ;;

  *)
    echo "Unknown action '${ACTION}'. Use: list, create, delete"
    exit 1
    ;;

esac

rm -f "${TMPFILE}"
