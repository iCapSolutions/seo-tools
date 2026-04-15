# seo-tools

A shared SEO and content toolkit for managing WordPress sites and non-WordPress
template-based sites via the command line. Designed to be a plug-in service
usable by any project repo — just set your env vars and point at your files.

Supports:
- **WordPress** sites (via REST API + Rank Math)
- **Template-based / static sites** (Perl, PHP, HTML — audit local files directly)

## Quick start

### 1. Clone into your projects directory

```sh
git clone https://github.com/iCapSolutions/seo-tools.git
cd seo-tools
```

### 2. Set environment variables

WordPress operations require:

```sh
export WP_SITE_URL=https://www.yoursite.com
export WP_USERNAME=your_user
export WP_APP_PASSWORD="your app password"
```

SEO rank checking requires:

```sh
export SERPAPI_KEY=your_serpapi_key
export TARGET_DOMAIN=yoursite.com
```

GA4 Realtime reporting requires a service account key and gcloud:

```sh
# Activate your service account once:
gcloud auth activate-service-account --key-file=/path/to/ga4-reader-key.json

# Query a specific property:
export GA4_PROPERTY_ID=your_9_digit_property_id
python3 scripts/ga4_active_users.py

# Or query all configured properties at once:
python3 scripts/ga4_active_users.py --all
```

See [GA4 Realtime setup](#ga4-realtime-setup) below for full one-time setup steps.

WooCommerce operations (optional) require:

```sh
export WC_SITE_URL=https://www.yoursite.com
export WC_CONSUMER_KEY=ck_xxxxx
export WC_CONSUMER_SECRET=cs_xxxxx
```

Image uploads optionally use:

```sh
export UNSPLASH_ACCESS_KEY=your_key  # falls back to loremflickr if not set
```

### 3. Per-project keywords

Create a `seo-keywords.txt` file in your **project** directory (not in seo-tools) with one focus keyword per line:

```
cloud consulting services
DevSecOps services
cloud cost optimization
```

Then run rank checks from your project directory:

```sh
python3 /path/to/seo-tools/scripts/check_seo_rank.py
```

The script reads `seo-keywords.txt` from wherever you run it.

## Scripts

### Content & publishing

| Script | Purpose |
|---|---|
| `fetch_wp_page.sh` | List all pages, or fetch a single page by ID or slug |
| `update_wp_page.sh` | Push revised HTML to a WordPress page or post (draft by default) |
| `manual_publish_wordpress.sh` | One-off test post to validate credentials |
| `update_wp_post_tags.sh` | Update categories and tags on a post |
| `manage_wp_taxonomy.sh` | Create, delete, or list tags and categories |

### Images

| Script | Purpose |
|---|---|
| `add_wp_image.sh` | Fetch a keyword image and upload to WP media |
| `pick_wp_image.sh` | Upload 3 candidate images for comparison |

### SEO

|| Script | Purpose |
||---|---|
|| `audit_html_seo.py` | Audit local HTML/SHTML files or live URLs for SEO issues (platform-agnostic) |
|| `verify_live_seo.py` | Quick post-deploy spot-check — confirm key SEO tags are present on a live page |
|| `check_seo_rank.py` | Check Google ranking for your focus keywords (SerpApi) |
|| `check_rankmath_seo.py` | Validate Rank Math SEO completeness for a page (WordPress only) |
|| `ga4_active_users.py` | Query GA4 Realtime API for active users (last N minutes, with optional breakdowns) |
|| `gsc_search_analytics.py` | Query Google Search Console Search Analytics API for clicks, impressions, CTR, and rankings |

### WooCommerce

| Script | Purpose |
|---|---|
| `wc.py` | Full WooCommerce CLI — products, orders, customers, categories, reports |

### Helpers (used internally by the shell scripts)

| Script | Purpose |
|---|---|
| `_wp_build_payload.py` | Build JSON body for update_wp_page.sh |
| `_wp_rankmath_payload.py` | Build Rank Math updateMeta payload |
| `_wp_page_summary.py` | Pretty-print WP REST API responses |
| `_wp_extract_fields.py` | Extract fields from WP JSON responses |

## SEO workflow

Three scripts cover the full cycle from editing to monitoring:

```
audit → fix → deploy → verify → monitor
```

### Step 1 — Audit before you edit

Run against a local file or directory to find issues before committing:

```sh
python3 scripts/audit_html_seo.py path/to/templates/home.html
python3 scripts/audit_html_seo.py path/to/templates/   # whole directory
```

Checks: `<title>`, `<meta description>`, viewport, canonical, Open Graph,
Twitter Card, `<main>` landmark, heading structure, image `alt` attributes,
unlabelled form inputs. Exit code 1 on any error-level finding.

### Step 2 — Fix, commit, and deploy

Edit the template file, commit to a feature branch, open a PR, and merge.
For git-deployed sites (like mailaddiction) the deploy triggers automatically.

### Step 3 — Verify the live page

After every deploy, confirm the changes landed in the rendered HTML
(catches issues from server-side includes, CDN caching, or redirects):

```sh
python3 scripts/verify_live_seo.py https://www.yoursite.com/
```

Checks: title, description, viewport, canonical, og:type/url/title/image,
twitter:card, `<main>`, `<h1>`. Green ✓ / red ✗ per tag, exit 1 if any
required tag is missing.

### Step 4 — Monitor rankings

Track keyword positions over time. Create `seo-keywords.txt` in your project
directory (one keyword per line), then run from that directory:

```sh
cd /path/to/your-project
export SERPAPI_KEY=your_key
export TARGET_DOMAIN=yoursite.com
python3 /path/to/seo-tools/scripts/check_seo_rank.py
```

---

## GA4 Realtime setup

One-time setup to enable `ga4_active_users.py`. The same service account works
across all your GA4 properties — you only create it once.

### 1 — Enable the required GCP APIs

In the [Google Cloud Console](https://console.cloud.google.com/apis/library),
enable both APIs for your project:
- **Google Analytics Data API** (`analyticsdata.googleapis.com`)
- **Google Analytics Admin API** (`analyticsadmin.googleapis.com`)

Or via gcloud:

```sh
gcloud services enable analyticsdata.googleapis.com analyticsadmin.googleapis.com \
  --project=YOUR_GCP_PROJECT_ID
```

### 2 — Create a service account

```sh
gcloud iam service-accounts create ga4-reader \
  --display-name="GA4 Reader" \
  --project=YOUR_GCP_PROJECT_ID

gcloud iam service-accounts keys create ~/ga4-reader-key.json \
  --iam-account=ga4-reader@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com
```

### 3 — Grant access in GA4 (repeat for each property)

For each site you want to monitor, go to:
GA4 → Admin → **Property Access Management** → Add users
- Email: `ga4-reader@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com`
- Role: **Viewer**

The service account only sees properties it has been explicitly invited to.

### 4 — Activate the service account

```sh
gcloud auth activate-service-account \
  --key-file=/path/to/ga4-reader-key.json
```

This persists in your gcloud config — you only need to run it once per machine.

### 5 — Register properties in the script

Open `scripts/ga4_active_users.py` and add each site to `KNOWN_PROPERTIES`:

```python
KNOWN_PROPERTIES = {
    "yoursite.com":    "123456789",   # GA4 property ID
    "anothersite.com": "987654321",
}
```

Find the numeric Property ID in GA4 → Admin → Property Settings → **Property ID**.

Alternatively, once the service account has access, list all your properties:

```sh
TOKEN=$(gcloud auth print-access-token \
  --scopes=https://www.googleapis.com/auth/analytics.readonly)
curl -s "https://analyticsadmin.googleapis.com/v1beta/properties?filter=parent:accounts/-" \
  -H "Authorization: Bearer $TOKEN"
```

### Auth options

The script tries authentication in this order:

1. `GA4_ACCESS_TOKEN` env var — paste a token directly (e.g. from [OAuth Playground](https://developers.google.com/oauthplayground), scope: `analytics.readonly`)
2. `GOOGLE_APPLICATION_CREDENTIALS` env var pointing to a service account JSON + `pip install google-auth`
3. `gcloud auth activate-service-account --key-file=...` (recommended)

### Usage examples

```sh
# All configured properties — summary table
python3 scripts/ga4_active_users.py --all

# Single property by ID
python3 scripts/ga4_active_users.py 309879063

# Single property via env var
export GA4_PROPERTY_ID=309879063
python3 scripts/ga4_active_users.py

# Narrow the window to ~"right now"
python3 scripts/ga4_active_users.py --all --minutes 5

# Per-minute breakdown for one site
python3 scripts/ga4_active_users.py 309879063 --breakdown

# Breakdown by country / page / device / city
python3 scripts/ga4_active_users.py 309879063 --by country
python3 scripts/ga4_active_users.py 309879063 --by page
python3 scripts/ga4_active_users.py 309879063 --by device
python3 scripts/ga4_active_users.py 309879063 --by city
```

---

## Google Search Console setup

One-time setup to enable `gsc_search_analytics.py`. The same service account works
for all your Search Console properties — you only set it up once.

### 1 — Enable the Search Console API

In the [Google Cloud Console](https://console.cloud.google.com/apis/library),
enable the API for your project:
- **Google Search Console API** (`searchconsole.googleapis.com`)

Or via gcloud:

```sh
gcloud services enable searchconsole.googleapis.com \
  --project=YOUR_GCP_PROJECT_ID
```

### 2 — Grant the service account access in Search Console

For each site you want to query, go to:
Search Console → **Settings** → **Users and permissions** → **Invite users**
- Email: `ga4-reader@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com`
- Role: **Owner** or **Full** access (minimum needed for Search Analytics API)

Alternatively, use the `gcloud` CLI to manage permissions if your GCP account has the necessary IAM roles.

### 3 — Register properties in the script

Open `scripts/gsc_search_analytics.py` and add each site to `KNOWN_SITES`.
Use the **URL-prefix format** (as shown in Search Console) — e.g., `https://www.example.com/`:

```python
KNOWN_SITES = {
    "yoursite.com":     "https://www.yoursite.com/",
    "anothersite.com":  "https://www.anothersite.com/",
}
```

To list all properties your service account can access:

```sh
python3 scripts/gsc_search_analytics.py --all
```

If you see a 403 permission error, verify the service account has been invited to that property in Search Console.

### Auth options

The script tries authentication in this order:

1. `GSC_ACCESS_TOKEN` env var — paste a token directly (e.g. from [OAuth Playground](https://developers.google.com/oauthplayground), scope: `webmasters.readonly`)
2. `GOOGLE_APPLICATION_CREDENTIALS` env var pointing to a service account JSON + `pip install google-auth`
3. `gcloud auth activate-service-account --key-file=...` (recommended, reuses your GA4 service account)

### Usage examples

```sh
# All configured properties — last 90 days, grouped by query
python3 scripts/gsc_search_analytics.py --all

# Single site — last 90 days, grouped by query
python3 scripts/gsc_search_analytics.py https://www.yoursite.com/

# Last 7 days
python3 scripts/gsc_search_analytics.py https://www.yoursite.com/ --days 7

# Breakdown by country
python3 scripts/gsc_search_analytics.py https://www.yoursite.com/ --by country

# Breakdown by device (DESKTOP, MOBILE, TABLET)
python3 scripts/gsc_search_analytics.py https://www.yoursite.com/ --by device

# Breakdown by page
python3 scripts/gsc_search_analytics.py https://www.yoursite.com/ --by page

# Multiple dimensions at once (query + country)
python3 scripts/gsc_search_analytics.py https://www.yoursite.com/ --by query --by country

# Last 30 days, all sites, grouped by device
python3 scripts/gsc_search_analytics.py --all --days 30 --by device
```

Output is a formatted table with:
- **Clicks** — number of clicks from Google Search results
- **Impressions** — how many times your URL appeared in results
- **CTR** — click-through rate (Clicks / Impressions)
- **Position** — average ranking position

---

## Using with existing projects

### Option A — Symlink scripts into your project

```sh
cd /path/to/your-site-repo
ln -s /path/to/seo-tools/scripts scripts/seo-tools
```

### Option B — Run directly with full path

```sh
/path/to/seo-tools/scripts/fetch_wp_page.sh
/path/to/seo-tools/scripts/check_seo_rank.py --domain yoursite.com
```

### Option C — Add to PATH

```sh
export PATH="/path/to/seo-tools/scripts:$PATH"
```

## Documentation

- [Page grooming workflow](docs/page-grooming.md) — step-by-step guide for reviewing and rewriting WordPress pages
- [WordPress operations](docs/wordpress-operations.md) — full scripts reference and publishing details
- [MailAddiction SEO](docs/mailaddiction-seo.md) — workflow for template-based / git-deployed sites (Perl/Apache)

## Requirements

- bash (3.2+)
- python3 (standard library only — no pip dependencies)
- curl
- **For template-based sites:** no external dependencies — just point at your HTML files
- **For WordPress operations:** WordPress with REST API enabled and an application password
- **For Rank Math fields:** Rank Math plugin
- **For rank checking:** SerpApi key (250 free searches/month)
- **For GA4 Realtime reporting:** gcloud CLI + a GCP service account with GA4 Viewer access

## Future

This project started as internal tooling for [iCapSolutions](https://www.icapsolutions.com) and [MadKrab](https://www.madkrab.com). The long-term goal is to make this a plug-in SEO service usable by any project repo — WordPress or otherwise — via a shared scripts directory or eventually a standalone open-source package.
