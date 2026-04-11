# SEO operations — MailAddiction (template-based site)

MailAddiction is a Perl/mod_perl site with HTML templates served via Apache.
There is no CMS API — content is managed by editing files in the git repo
and merging to `main`, which auto-deploys to the live EC2 in ~27 seconds.

This doc covers the complete SEO workflow for this architecture.

---

## Setup

No API credentials needed for auditing or editing. For rank tracking:

```sh
export SERPAPI_KEY=your_key
export TARGET_DOMAIN=mailaddiction.com
```

The `seo-keywords.txt` file lives in the mailaddiction repo root.
Run rank checks from that directory:

```sh
cd /path/to/mailaddiction
python3 /path/to/seo-tools/scripts/check_seo_rank.py
```

---

## Workflow: edit a template page

### Step 1 — Audit the target file

```sh
python3 /path/to/seo-tools/scripts/audit_html_seo.py \
  /path/to/mailaddiction/templates/home.html
```

Or audit all templates at once:

```sh
python3 /path/to/seo-tools/scripts/audit_html_seo.py \
  /path/to/mailaddiction/templates/
```

Or audit the live rendered page (checks what users and crawlers actually see,
including content from server-side includes):

```sh
python3 /path/to/seo-tools/scripts/audit_html_seo.py \
  --live https://www.mailaddiction.com/
```

### Step 2 — Edit the template file locally

Templates live in `mailaddiction/templates/`. The active public-facing pages are:

| File | URL |
|---|---|
| `templates/home.html` | `mailaddiction.com/` |
| `templates/features.html` | `mailaddiction.com/features.html` |
| `templates/pricing.html` | `mailaddiction.com/pricing.html` |
| `templates/about.html` | `mailaddiction.com/about.html` |
| `templates/trial.html` | `mailaddiction.com/trial.html` |
| `templates/header.html` | sitewide header include |
| `templates/footer.html` | sitewide footer include |

Note: templates use two include mechanisms simultaneously:
- `<!--TMPL_INCLUDE NAME="file.html"-->` — Perl HTML::Template (mod_perl)
- `<!--#include file="file.html"-->` — Apache SSI

Both resolve to the same files. Edit the source file; both includes update.

### Step 3 — Create a feature branch and commit

```sh
cd /path/to/mailaddiction
git checkout -b seo/homepage-improvements
git add templates/home.html
git commit -m "SEO: add viewport, canonical, OG tags, <main> landmark"
git push origin seo/homepage-improvements
```

### Step 4 — Open a PR and merge

```sh
gh pr create --title "SEO improvements: home.html" \
  --body "Adds viewport, canonical, full OG tags, Twitter Card, <main> landmark"
gh pr merge --squash
```

Merge triggers the deploy pipeline automatically (~27s to live).

### Step 5 — Verify the live page

```sh
# Quick check of key meta tags
curl -s -H "User-Agent: Mozilla/5.0 Chrome/120.0" \
  https://www.mailaddiction.com/ | \
  python3 -c "
import sys, re
html = sys.stdin.read()
title = re.search(r'<title>(.*?)</title>', html)
desc  = re.search(r'<meta name=\"description\" content=\"(.*?)\"', html)
vp    = re.search(r'<meta name=\"viewport\" content=\"(.*?)\"', html)
canon = re.search(r'<link rel=\"canonical\" href=\"(.*?)\"', html)
print('Title:     ', title.group(1) if title else 'MISSING')
print('Desc:      ', (desc.group(1)[:80] + '…') if desc else 'MISSING')
print('Viewport:  ', vp.group(1) if vp else 'MISSING')
print('Canonical: ', canon.group(1) if canon else 'MISSING')
"

# Or run a full audit against the live URL
python3 /path/to/seo-tools/scripts/audit_html_seo.py \
  --live https://www.mailaddiction.com/
```

### Step 6 — Check rankings

```sh
cd /path/to/mailaddiction
python3 /path/to/seo-tools/scripts/check_seo_rank.py
```

---

## Key SEO facts for this site

### What the audit already found and fixed (2026-04-11)

Applied to `templates/home.html`:
- Added `<meta name="viewport">` (was missing — critical for mobile ranking)
- Fixed `<meta name="Description">` → lowercase `description` (case matters)
- Added `<link rel="canonical" href="https://www.mailaddiction.com/">`
- Added full Open Graph tags: `og:type`, `og:url`, `og:title`, `og:description`
  (og:image was already present; upgraded to HTTPS URL)
- Added Twitter Card tags: `twitter:card`, `twitter:title`, `twitter:description`
- Added `<main>` landmark around main content (accessibility + SEO)
- Fixed `type="type"` typo on login email input → `type="text"`
- Added `aria-label` to login form inputs (`login_name`, `login_password`)

### Remaining known issues (see LIGHTHOUSE.md for full list)

- Low-contrast text on some elements
- Some decorative `<img src="spacer.gif" alt="">` — intentional, correct treatment
- No structured data / Schema.org markup — future improvement
- CloudFront cutover pending (will improve TTFB/Core Web Vitals significantly)
- PHP 7.3 on the EC2 is EOL — upgrade as part of Phase 3

### Architecture notes for SEO work

- Templates are rendered by Perl `HTML::Template` at request time — changes
  go live immediately on deploy, no cache to bust
- The WordPress install (`/wordpress/`) is gitignored — WordPress SEO is
  managed separately (see `wordpress-operations.md`)
- `conf/README` and `conf/README.txt` are gitignored — contain old credentials
- `generator/data/sitemap.xml` and `templates/sitemap.xml` are generated by
  the PHP sitemap crawler and are gitignored — don't edit manually
- Server is behind the `lb-icap` ALB on AWS — the ALB terminates TLS,
  so the EC2 sees HTTP internally

---

## Focus keywords

See `mailaddiction/seo-keywords.txt`. Current targets:

- email marketing service
- affordable email marketing
- email campaign software
- email list management
- bulk email marketing
- email marketing platform
- email blast service
- email campaign management

---

## Notes

- The `audit_html_seo.py` script audits local template files. Some checks
  (e.g. `<main>`, heading content) may warn about things that are actually
  provided by server-side includes — always verify with `--live` after deploy.
- `main` branch is protected — all changes require a PR. This also means
  every SEO change goes through review before hitting production.
