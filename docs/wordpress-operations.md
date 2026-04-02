# WordPress operations

Scripts for managing WordPress content, taxonomy, images, and SEO via the REST API.

## Required environment variables

- `WP_SITE_URL` — your WordPress site URL (e.g. `https://www.example.com`)
- `WP_USERNAME` — WordPress username with REST API access
- `WP_APP_PASSWORD` — WordPress application password

## Publishing

Automated publishing uses the WordPress REST API:
- Endpoint: `POST $WP_SITE_URL/wp-json/wp/v2/posts`
- Auth: Basic auth (`$WP_USERNAME:$WP_APP_PASSWORD`)
- Required fields: `title`, `content`, `status`

## Scripts reference

### Content & publishing

**`scripts/manual_publish_wordpress.sh [title] [html]`**
Send a one-off test post as a draft. Useful for validating credentials and payload format.

**`scripts/update_wp_page.sh <page-id> <html-file> [status] [title] [meta-desc] [focus-kw] [featured-id] [slug]`**
Push revised HTML content back to a WordPress page or post. Saves as `draft` by default.
Set `POST_TYPE=posts` env var to target posts instead of pages.
Also writes Rank Math SEO meta (`meta-desc`, `focus-kw`) if provided.

### Taxonomy (categories & tags)

**`scripts/manage_wp_taxonomy.sh <list|create|delete> <tags|categories> [args...]`**
Manage the global tag and category vocabularies.
- `list tags` / `list categories` — show all terms with ID, slug, name, and usage count
- `create tags "Name" [slug]` / `create categories "Name" [slug]` — create a new term
- `delete tags <id>` / `delete categories <id>` — permanently delete a term

**`scripts/update_wp_post_tags.sh <post-id> <categories-csv> <tags-csv>`**
Update categories and/or tags on any WordPress post via the REST API.
Pass comma-separated IDs. Content and status are not touched.

### Images

**`scripts/add_wp_image.sh <keywords> [width] [height]`**
Fetch a keyword-matched image from Unsplash (requires `UNSPLASH_ACCESS_KEY`) or fall back to loremflickr. Uploads to WordPress media library and prints the media ID.

**`scripts/pick_wp_image.sh <keywords> [width] [height] [alt-b-kw] [alt-c-kw]`**
Uploads 3 candidate images and lists their media IDs. Preview in WP Admin → Media Library.

### SEO

**`scripts/check_seo_rank.py [keyword] [--depth N] [--domain DOMAIN]`**
Check where your site ranks on Google for its focus keywords. Uses SerpApi (`SERPAPI_KEY`). Each keyword costs 1 search credit.
- No args — checks all keywords in `seo-keywords.txt`
- `"keyword"` — checks a single keyword (1 credit)
- `--depth N` — how many results deep to scan (default: 20)
- `--domain DOMAIN` — override `TARGET_DOMAIN` env var

**`scripts/check_rankmath_seo.py <page-id> <focus-keyword>`**
Validate Rank Math SEO requirements for a page or post. Checks keyword in title, description, content, and length targets.

### WooCommerce

**`scripts/wc.py <resource> <action> [args...]`**
CLI for WooCommerce REST API — manage products, variations, orders, customers, categories, and reports.
Requires: `WC_CONSUMER_KEY`, `WC_CONSUMER_SECRET`, `WC_SITE_URL`.

### Helpers (internal use)

- **`scripts/_wp_build_payload.py`** — Builds JSON body for `update_wp_page.sh`
- **`scripts/_wp_rankmath_payload.py`** — Builds Rank Math `updateMeta` payload
- **`scripts/_wp_page_summary.py`** — Parses WP REST API response and prints a human-readable summary
- **`scripts/_wp_extract_fields.py`** — Extracts dot-path fields from WP REST API JSON responses

## Notes

- **WAF/BotControl:** All scripts include `-H "User-Agent: Mozilla/5.0 Chrome/120.0"`. Plain curl may be blocked by WAF. Any new scripts or one-off curl commands to your site must include this header.
