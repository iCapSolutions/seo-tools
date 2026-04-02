#!/usr/bin/env python3
"""
check_rankmath_seo.py

Validate Rank Math SEO requirements for a WordPress page or post.

Usage:
    python3 scripts/check_rankmath_seo.py <page_id> <focus_keyword>
    python3 scripts/check_rankmath_seo.py 161 "customer support"

Validates:
  - Focus keyword appears in SEO title
  - Focus keyword appears in SEO meta description
  - Focus keyword appears in page content
  - SEO title length (optimal 50-60 chars)
  - SEO description length (optimal 150-160 chars)

Requires: WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD env vars
"""

import json
import urllib.request
import base64
import os
import sys
from html.parser import HTMLParser


class TextExtractor(HTMLParser):
    """Extract plain text from HTML."""
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get(self):
        return ''.join(self.text).lower()


def fetch_page(page_id):
    wp_site_url = os.environ.get('WP_SITE_URL', '').rstrip('/')
    wp_username = os.environ.get('WP_USERNAME', '')
    wp_app_password = os.environ.get('WP_APP_PASSWORD', '')

    if not wp_site_url:
        print('Error: WP_SITE_URL not set')
        sys.exit(1)
    if not wp_app_password:
        print('Error: WP_APP_PASSWORD not set')
        sys.exit(1)

    auth = base64.b64encode(f'{wp_username}:{wp_app_password}'.encode()).decode()

    # Try pages first, then posts
    for post_type in ('pages', 'posts'):
        req = urllib.request.Request(
            f'{wp_site_url}/wp-json/wp/v2/{post_type}/{page_id}',
            headers={
                'Authorization': f'Basic {auth}',
                'User-Agent': 'Mozilla/5.0 Chrome/120.0',
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            print(f'Error fetching {post_type}/{page_id}: {e}')
            sys.exit(1)
        except Exception as e:
            print(f'Error fetching page: {e}')
            sys.exit(1)

    print(f'Error: ID {page_id} not found as page or post')
    sys.exit(1)


def fetch_live_meta(page_url):
    """Fetch live meta title/description from rendered page."""
    import re
    try:
        req = urllib.request.Request(
            page_url,
            headers={'User-Agent': 'Mozilla/5.0 Chrome/120.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode()

        title_match = re.search(r'<title>(.*?)</title>', html)
        desc_match  = re.search(r'<meta name="description" content="(.*?)"', html)

        title = title_match.group(1) if title_match else ''
        desc  = desc_match.group(1)  if desc_match  else ''

        title = title.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', "'")
        desc  = desc.replace('&amp;',  '&').replace('&quot;', '"').replace('&#039;', "'")

        return title, desc
    except Exception as e:
        print(f'Warning: Could not fetch live meta: {e}')
        return '', ''


def main():
    if len(sys.argv) < 3:
        print('Usage: python3 check_rankmath_seo.py <page_id> <focus_keyword>')
        print('Example: python3 check_rankmath_seo.py 161 "customer support"')
        sys.exit(1)

    page_id       = sys.argv[1]
    focus_keyword = ' '.join(sys.argv[2:])

    page          = fetch_page(page_id)
    page_title    = page.get('title', {}).get('rendered', '')
    page_link     = page.get('link', '')
    content_html  = page.get('content', {}).get('rendered', '')

    extractor = TextExtractor()
    extractor.feed(content_html)
    content_text = extractor.get()

    live_title, live_desc = fetch_live_meta(page_link)
    focus_kw_lower = focus_keyword.lower()

    print(f'\n  Rank Math SEO Check — {os.environ.get("WP_SITE_URL", "")}')
    print(f'  Page {page_id}: {page_title}')
    print('  ' + '─' * 60)
    print(f'  Focus Keyword: "{focus_keyword}"')
    print(f'  Page URL: {page_link}')
    print()
    print('  Live Meta Tags:')
    print(f'    Title: {live_title}')
    print(f'    Desc:  {live_desc}')
    print()
    print('  Validation Checks:')
    print('  ' + '─' * 60)

    checks = [
        (
            'Focus keyword in SEO title',
            focus_kw_lower in live_title.lower(),
            f'Expected: "{focus_keyword}" in title'
        ),
        (
            'Focus keyword in SEO description',
            focus_kw_lower in live_desc.lower(),
            f'Expected: "{focus_keyword}" in description'
        ),
        (
            'Focus keyword in page content',
            focus_kw_lower in content_text,
            f'Expected: "{focus_keyword}" appears in content'
        ),
        (
            f'SEO title length ({len(live_title)} chars)',
            50 <= len(live_title) <= 60,
            'Target: 50-60 characters'
        ),
        (
            f'SEO description length ({len(live_desc)} chars)',
            150 <= len(live_desc) <= 160,
            'Target: 150-160 characters'
        ),
    ]

    passed = 0
    failed = 0
    for check_name, result, hint in checks:
        status = '✅' if result else '❌'
        print(f'  {status} {check_name}')
        if not result:
            print(f'     {hint}')
            failed += 1
        else:
            passed += 1

    print('  ' + '─' * 60)
    print(f'  {passed}/{len(checks)} checks passed')
    print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
