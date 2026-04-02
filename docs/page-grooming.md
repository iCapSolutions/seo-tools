# WordPress page grooming

Review and rewrite existing WordPress pages using seo-tools scripts.

## Required env vars

- `WP_SITE_URL` — your WordPress site (e.g. `https://www.example.com`)
- `WP_USERNAME`
- `WP_APP_PASSWORD`

## Scripts

| Script | Purpose |
|---|---|
| `scripts/fetch_wp_page.sh` | List all pages, or fetch a single page by ID or slug |
| `scripts/update_wp_page.sh` | Push revised HTML back to WordPress (draft by default) |
| `scripts/add_wp_image.sh` | Fetch a keyword image from Unsplash/loremflickr, upload to WP media, return media ID |
| `scripts/pick_wp_image.sh` | Fetch **3 image options** (A/B/C) and upload all — preview in WP Admin, then pick the best media ID |

## Workflow

### Step 1 — Find the page

```sh
./scripts/fetch_wp_page.sh
```

Lists all pages with their `id`, `slug`, `title`, and `status`.

### Step 2 — Fetch the page content

```sh
./scripts/fetch_wp_page.sh <id>
# or by slug:
./scripts/fetch_wp_page.sh about
```

Shows metadata, all links (internal/external), images with alt text warnings, and the page content as plain text.

Note: `content.raw` (Gutenberg block source) is not accessible via the REST API without elevated permissions. Work from `content.rendered` instead.

### Step 3 — Revise the content

Produce revised HTML and save it to a file:

```sh
cat > /tmp/page-revised.html << 'EOF'
<revised HTML here>
EOF
```

### Step 4 — Push back as draft

```sh
./scripts/update_wp_page.sh <id> /tmp/page-revised.html
```

Saves as **draft** by default. Review in WP admin before publishing.

### Step 5 — Publish (when satisfied)

```sh
./scripts/update_wp_page.sh <id> /tmp/page-revised.html publish
```

## Images

### Displaying an image on the page
Embed it as an `<img>` tag in the HTML file:
```html
<figure class="wp-block-image size-large">
  <img src="https://yoursite.com/wp-content/uploads/..." alt="Descriptive alt text" class="wp-image-XXXX" style="width:100%;height:auto;margin-bottom:1.5em;" />
</figure>
```

### Featured image (social/SEO only)
Arg 7 of `update_wp_page.sh` sets `featured_media` — this controls the image used for social share previews (Open Graph) and search engine image previews. It does **not** embed an image in the page body.

For full coverage, do both: embed the `<img>` in the HTML content AND pass the media ID as arg 7.

### Getting a new image
```sh
# Standard (1600x900)
MEDIA_ID=$(./scripts/add_wp_image.sh "your keywords here" | tail -1)

# Banner/wide format (1600x450)
MEDIA_ID=$(./scripts/add_wp_image.sh "your keywords here" 1600 450 | tail -1)
```
Uses `UNSPLASH_ACCESS_KEY` if set; falls back to loremflickr.com (free, no key needed).

### Picking from 3 image options
```sh
./scripts/pick_wp_image.sh "cloud devops technology" 1600 450
```
Uploads all three to WP media. Preview in **WP Admin → Media Library**, then apply the best one:
```sh
./scripts/update_wp_page.sh <page-id> <html-file> publish "" "" "" <chosen-media-id>
```

### Image alt text
Every `<img>` must have a descriptive `alt` attribute for SEO and accessibility. `fetch_wp_page.sh` flags images with empty alt text with `⚠ empty alt`.

## Rank Math SEO fields

Fields can be set via `update_wp_page.sh` (args 5 and 6) or directly via the Rank Math REST API:

- `rank_math_description` — meta description shown in search results
- `rank_math_focus_keyword` — focus keyphrase used for SEO scoring
- `rank_math_title` — custom SEO title (overrides page title in search results)

**Note:** Rank Math meta fields are **not** exposed via the standard WP REST API `meta` object. `fetch_wp_page.sh` will always show `(set via Rank Math — verify in WP Admin)` regardless. Verify by curling the live page `<head>` or checking WP Admin → Rank Math panel.

### Setting SEO fields via Rank Math API

```python
import json, urllib.request, base64, os

auth = base64.b64encode(
    f'{os.environ["WP_USERNAME"]}:{os.environ["WP_APP_PASSWORD"]}'.encode()
).decode()

payload = json.dumps({
    'objectType': 'post',
    'objectID':   <page_id>,
    'meta': {
        'rank_math_focus_keyword': 'your focus keyword',
        'rank_math_description':   'Your meta description (150-160 chars).',
        'rank_math_title':         'SEO Title | Your Site',
    }
}).encode()

req = urllib.request.Request(
    f'{os.environ["WP_SITE_URL"]}/wp-json/rankmath/v1/updateMeta',
    data    = payload,
    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type':  'application/json',
        'User-Agent':    'Mozilla/5.0 Chrome/120.0',
    },
    method = 'POST'
)
with urllib.request.urlopen(req, timeout=15) as resp:
    result = json.loads(resp.read().decode())
print('ok' if result.get('slug') else result)
```

### Verifying fields are live

```sh
curl -s -H "User-Agent: Mozilla/5.0 Chrome/120.0" https://yoursite.com/ | \
  python3 -c "
import sys, re
html = sys.stdin.read()
title = re.search(r'<title>(.*?)</title>', html)
desc  = re.search(r'<meta name=\"description\" content=\"(.*?)\"', html)
print('Title:', title.group(1) if title else 'NOT FOUND')
print('Desc: ', desc.group(1) if desc else 'NOT FOUND')
"
```

## Slug

Writable via arg 8:
```sh
./scripts/update_wp_page.sh <id> <file> publish "Title" "" "" "" "new-slug"
```
WordPress preserves old URLs as redirects when a slug changes on a published page.

## Notes

- The update script uses `python3` to safely JSON-encode HTML content.
- `content.rendered` is the final HTML rendered by WordPress.
- Changes are saved as draft unless `publish` is explicitly passed as arg 3.
- **WAF/BotControl:** All scripts include `-H "User-Agent: Mozilla/5.0 Chrome/120.0"`. Plain curl may be blocked by WAF. Any new scripts or one-off curl commands must include this header.
