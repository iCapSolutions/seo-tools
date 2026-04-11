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

| Script | Purpose |
|---|---|
| `audit_html_seo.py` | Audit local HTML/SHTML files or live URLs for SEO issues (platform-agnostic) |
| `check_seo_rank.py` | Check Google ranking for your focus keywords (SerpApi) |
| `check_rankmath_seo.py` | Validate Rank Math SEO completeness for a page (WordPress only) |

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

## Future

This project started as internal tooling for [iCapSolutions](https://www.icapsolutions.com) and [MadKrab](https://www.madkrab.com). The long-term goal is to make this a plug-in SEO service usable by any project repo — WordPress or otherwise — via a shared scripts directory or eventually a standalone open-source package.
