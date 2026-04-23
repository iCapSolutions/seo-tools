#!/usr/bin/env python3
"""sitemap_crawl — lightweight crawler that generates sitemap.xml

Starts at a root URL, follows same-domain links naturally (like a search
engine), and outputs a standards-compliant XML sitemap.

Usage:
    python3 sitemap_crawl.py https://www.example.com/
    python3 sitemap_crawl.py https://www.example.com/ -o sitemap.xml
    python3 sitemap_crawl.py https://www.example.com/ -o sitemap.xml --delay 1.0
    python3 sitemap_crawl.py https://www.example.com/ -o sitemap.xml \
        --include-prefix /articles --include-prefix /resources \
        --exclude-prefix /secure --exclude-prefix /admin

Cron (weekly Sunday 3am):
    0 3 * * 0 python3 /opt/seo-tools/sitemap_crawl.py https://www.mailaddiction.com/ \
        -o /var/www/mailadiction/templates/sitemap.xml 2>>/var/log/sitemap_crawl.log
"""

import argparse
import gzip
import os
import re
import sys
import time
from collections import deque
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

# ── Config ────────────────────────────────────────────────
LINK_RE = re.compile(r'<a\s[^>]*?href=["\']([^"\']+)["\']', re.IGNORECASE)
META_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)

SKIP_EXT = frozenset([
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".gz", ".tar", ".rar", ".7z",
    ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".m4v",
    ".css", ".js", ".json", ".xml", ".txt", ".csv",
    ".woff", ".woff2", ".ttf", ".eot",
])

DEFAULT_EXCLUDE_PREFIXES = (
    "/secure/",
    "/manager/",
    "/admin/",
    "/cgi-bin/",
    "/sitemap_ez",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip",
}


# ── Helpers ───────────────────────────────────────────────
def fetch(url, timeout=15):
    """Fetch a URL. Returns (status, body, last_modified)."""
    req = Request(url, headers=HEADERS)
    try:
        resp = urlopen(req, timeout=timeout)
        code = resp.getcode()
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        ctype = resp.headers.get("Content-Type", "")
        last_mod = resp.headers.get("Last-Modified")
        if "text/html" not in ctype:
            return code, "", last_mod
        body = raw.decode("utf-8", errors="ignore")
        return code, body, last_mod
    except HTTPError as e:
        return e.code, "", None
    except (URLError, OSError):
        return 0, "", None


def normalize_url(url, domain):
    """Force https, strip fragment/query, normalize trailing slashes."""
    p = urlparse(url)
    p = p._replace(scheme="https")
    p = p._replace(netloc=domain)
    p = p._replace(fragment="", query="")
    path = p.path
    if path == "" or path == "/":
        path = "/"
    else:
        path = path.rstrip("/")
    p = p._replace(path=path)
    return urlunparse(p)


def normalize_path(path):
    """Normalize a URL path for policy matching."""
    if not path or path == "/":
        return "/"
    return path.rstrip("/")


def normalize_prefix(prefix):
    """Normalize include/exclude prefixes to rooted path prefixes."""
    if not prefix:
        return "/"
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    return normalize_path(prefix)


def path_matches_prefix(path, prefix):
    """Return True if path is equal to prefix or under that path prefix."""
    if prefix == "/":
        return True
    return path == prefix or path.startswith(prefix + "/")


def has_noindex_meta(html):
    """Detect whether page HTML contains robots noindex metadata."""
    head = html[:12000]
    for meta in META_RE.findall(head):
        meta_l = meta.lower()
        if "robots" in meta_l and "noindex" in meta_l:
            return True
    return False


def extract_links(html, base_url, domain):
    """Pull same-domain page links from HTML."""
    links = []
    for m in LINK_RE.finditer(html):
        raw = m.group(1).strip()
        if raw.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(base_url, raw)
        p = urlparse(url)
        if p.netloc not in (domain, domain.replace("www.", "")) \
           or p.scheme not in ("http", "https"):
            continue
        ext = os.path.splitext(p.path)[1].lower()
        if ext in SKIP_EXT:
            continue
        clean = normalize_url(url, domain)
        links.append(clean)
    return links


def crawl(start_url, delay=0.5, max_pages=500, timeout=15, verbose=False):
    """BFS crawl from start_url. Returns page records with URL metadata."""
    domain = urlparse(start_url).netloc
    start_url = normalize_url(start_url, domain)
    visited = set()
    queue = deque([start_url])
    pages = []

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        code, body, last_mod = fetch(url, timeout=timeout)

        if verbose:
            print("  {:3d}  {}".format(code, url), file=sys.stderr)

        if code == 200 and body:
            pages.append({
                "url": url,
                "last_modified": last_mod,
                "noindex": has_noindex_meta(body),
            })
            for link in extract_links(body, url, domain):
                if link not in visited:
                    queue.append(link)

        if delay > 0:
            time.sleep(delay)

    return pages


def apply_url_policy(pages, include_prefixes=None, exclude_prefixes=None,
                     include_noindex=False):
    """Filter pages by include/exclude path prefixes and robots noindex."""
    include_prefixes = [normalize_prefix(p) for p in (include_prefixes or [])]
    exclude_prefixes = [normalize_prefix(p) for p in (exclude_prefixes or [])]

    filtered = []
    dropped_noindex = 0
    dropped_include = 0
    dropped_exclude = 0

    for page in pages:
        path = normalize_path(urlparse(page["url"]).path)

        if not include_noindex and page.get("noindex"):
            dropped_noindex += 1
            continue

        if include_prefixes and not any(
            path_matches_prefix(path, prefix) for prefix in include_prefixes
        ):
            dropped_include += 1
            continue

        if any(path_matches_prefix(path, prefix) for prefix in exclude_prefixes):
            dropped_exclude += 1
            continue

        filtered.append(page)

    stats = {
        "dropped_noindex": dropped_noindex,
        "dropped_include": dropped_include,
        "dropped_exclude": dropped_exclude,
    }
    return filtered, stats


def generate_sitemap(pages):
    """Generate XML sitemap string from filtered page records."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for page in sorted(pages, key=lambda item: item["url"]):
        url = page["url"]
        last_mod = page["last_modified"]
        lines.append("  <url>")
        lines.append("    <loc>{}</loc>".format(url))
        if last_mod:
            try:
                dt = datetime.strptime(last_mod, "%a, %d %b %Y %H:%M:%S %Z")
                lines.append("    <lastmod>{}</lastmod>".format(dt.strftime("%Y-%m-%d")))
            except ValueError:
                lines.append("    <lastmod>{}</lastmod>".format(now))
        else:
            lines.append("    <lastmod>{}</lastmod>".format(now))
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="Crawl a site and generate sitemap.xml"
    )
    p.add_argument("url", help="Start URL (e.g. https://www.example.com/)")
    p.add_argument("-o", "--output", help="Output file (default: stdout)")
    p.add_argument("--delay", type=float, default=0.5,
                   help="Delay between requests in seconds (default: 0.5)")
    p.add_argument("--max-pages", type=int, default=500,
                   help="Max pages to crawl (default: 500)")
    p.add_argument("--timeout", type=int, default=15,
                   help="Request timeout in seconds (default: 15)")
    p.add_argument("--include-prefix", action="append", default=[],
                   help="Only include URLs under this path prefix (repeatable)")
    p.add_argument("--exclude-prefix", action="append", default=[],
                   help="Exclude URLs under this path prefix (repeatable)")
    p.add_argument("--no-default-excludes", action="store_true",
                   help="Disable built-in path excludes (e.g., /secure/)")
    p.add_argument("--include-noindex", action="store_true",
                   help="Include pages with robots noindex metadata")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Print each URL as it's crawled")
    args = p.parse_args()

    start = args.url.rstrip("/") + "/"

    exclude_prefixes = list(args.exclude_prefix)
    if not args.no_default_excludes:
        exclude_prefixes = list(DEFAULT_EXCLUDE_PREFIXES) + exclude_prefixes

    print("Crawling {} ...".format(start), file=sys.stderr)
    t0 = time.time()
    discovered = crawl(
        start,
        delay=args.delay,
        max_pages=args.max_pages,
        timeout=args.timeout,
        verbose=args.verbose,
    )
    elapsed = time.time() - t0

    print("Discovered {} pages in {:.1f}s".format(len(discovered), elapsed), file=sys.stderr)

    pages, stats = apply_url_policy(
        discovered,
        include_prefixes=args.include_prefix,
        exclude_prefixes=exclude_prefixes,
        include_noindex=args.include_noindex,
    )

    print(
        "Included {} pages (dropped: {} noindex, {} include-policy, {} exclude-policy)".format(
            len(pages),
            stats["dropped_noindex"],
            stats["dropped_include"],
            stats["dropped_exclude"],
        ),
        file=sys.stderr,
    )

    sitemap = generate_sitemap(pages)

    if args.output:
        with open(args.output, "w") as f:
            f.write(sitemap)
        print("Wrote {}".format(args.output), file=sys.stderr)
    else:
        sys.stdout.write(sitemap)


if __name__ == "__main__":
    main()
