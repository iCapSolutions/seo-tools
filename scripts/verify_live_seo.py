#!/usr/bin/env python3
"""
verify_live_seo.py
Quick spot-check of key SEO tags on a live page.

Complements audit_html_seo.py (deep local file analysis) by confirming
that deployed changes are actually present in the rendered live HTML —
including content from server-side includes, CDN, or any other layer.

Usage:
    python3 scripts/verify_live_seo.py https://www.mailaddiction.com/
    python3 scripts/verify_live_seo.py https://example.com/about

Exit code: 0 if all required tags present, 1 if any are missing.

Checks:
    <title>
    <meta name="description">
    <meta name="viewport">
    <link rel="canonical">
    og:type, og:url, og:title, og:image
    twitter:card
    <main> landmark
    <h1>
"""

import sys
import re
import urllib.request
import urllib.error


RESET  = '\033[0m'
BOLD   = '\033[1m'
GREEN  = '\033[92m'
RED    = '\033[91m'
YELLOW = '\033[93m'
CYAN   = '\033[96m'
DIVIDER = '  ' + '─' * 68


def col(text, code): return f'{code}{text}{RESET}'


CHECKS = [
    # (label, regex, required)
    ('title',          r'<title[^>]*>(.*?)</title>',                                  True),
    ('description',    r'<meta\s[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', True),
    ('viewport',       r'<meta\s[^>]*name=["\']viewport["\'][^>]*content=["\'](.*?)["\']',    True),
    ('canonical',      r'<link\s[^>]*rel=["\']canonical["\'][^>]*href=["\'](.*?)["\']',        True),
    ('og:type',        r'<meta\s[^>]*property=["\']og:type["\'][^>]*content=["\'](.*?)["\']',  True),
    ('og:url',         r'<meta\s[^>]*property=["\']og:url["\'][^>]*content=["\'](.*?)["\']',   True),
    ('og:title',       r'<meta\s[^>]*property=["\']og:title["\'][^>]*content=["\'](.*?)["\']', True),
    ('og:image',       r'<meta\s[^>]*property=["\']og:image["\'][^>]*content=["\'](.*?)["\']', True),
    ('twitter:card',   r'<meta\s[^>]*name=["\']twitter:card["\'][^>]*content=["\'](.*?)["\']', False),
    ('<main>',         r'(<main[\s>])',                                                False),
    ('<h1>',           r'<h1[\s>]',                                                   False),
]


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 Chrome/120.0'}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace'), resp.geturl()
    except urllib.error.URLError as e:
        print(f'\n  {col("Error", RED)}: could not fetch {url}\n  {e}\n')
        sys.exit(1)


def shorten(val, max_len=65):
    return val[:max_len] + '…' if len(val) > max_len else val


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    url = sys.argv[1]
    if not url.startswith('http'):
        url = 'https://' + url

    print(f'\n{BOLD}  Verifying live SEO tags{RESET}')
    print(f'  {col(url, CYAN)}')
    print(DIVIDER)

    html, final_url = fetch(url)
    if final_url != url:
        print(f'  {col("Redirected to:", YELLOW)} {final_url}')

    missing_required = 0

    for label, pattern, required in CHECKS:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            # Get first capture group if present, else the full match
            val = m.group(1) if m.lastindex else '✓'
            val = shorten(val.strip())
            print(f'  {col("✓", GREEN)}  {label:<16} {val}')
        else:
            if required:
                print(f'  {col("✗", RED)}  {label:<16} {col("MISSING", RED)}')
                missing_required += 1
            else:
                print(f'  {col("–", YELLOW)}  {label:<16} {col("not found", YELLOW)}')

    print(DIVIDER)
    if missing_required == 0:
        print(f'  {col("✓ All required tags present", GREEN)}\n')
    else:
        print(f'  {col(f"✗ {missing_required} required tag(s) missing", RED)}\n')

    sys.exit(1 if missing_required else 0)


if __name__ == '__main__':
    main()
