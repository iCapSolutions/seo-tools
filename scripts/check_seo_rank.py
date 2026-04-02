#!/usr/bin/env python3
"""
check_seo_rank.py
Check where your site ranks on Google for its focus keywords.

Uses SerpApi — each keyword costs 1 search credit.

Usage:
    python3 scripts/check_seo_rank.py                      # all keywords in seo-keywords.txt
    python3 scripts/check_seo_rank.py "cloud consulting"   # single keyword
    python3 scripts/check_seo_rank.py --depth 30           # scan top 30 results (default: 20)

Keyword source (in order of precedence):
    1. Keyword passed as CLI argument
    2. seo-keywords.txt in the current working directory (one keyword per line)

Domain source (in order of precedence):
    1. TARGET_DOMAIN env var  (e.g. export TARGET_DOMAIN=icapsolutions.com)
    2. --domain argument      (e.g. --domain icapsolutions.com)

Requires: SERPAPI_KEY env var
"""

import sys
import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

DIVIDER = "  " + "─" * 68


def load_keywords_from_file():
    """Read seo-keywords.txt from cwd, one keyword per line, skip blanks/comments."""
    path = os.path.join(os.getcwd(), "seo-keywords.txt")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]


def search(query, num, api_key):
    params = {
        "engine":  "google",
        "q":       query,
        "num":     num,
        "api_key": api_key,
        "gl":      "us",
        "hl":      "en",
    }
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            msg = json.loads(body).get("error", body)
        except Exception:
            msg = body
        print(f"\n  HTTP {e.code}: {msg}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n  Request error: {e}\n")
        sys.exit(1)


def find_rank(results, domain):
    for item in results.get("organic_results", []):
        link = item.get("link", "")
        if domain in link:
            return item.get("position"), item.get("title", ""), link
    return None, None, None


def credits_remaining(api_key):
    url = "https://serpapi.com/account.json?" + urllib.parse.urlencode({"api_key": api_key})
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("plan_searches_left", "?")
    except Exception:
        return "?"


def shorten_url(url, max_len=52):
    url = url.replace("https://", "").replace("http://", "")
    return url if len(url) <= max_len else url[:max_len - 1] + "…"


def main():
    args = sys.argv[1:]

    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        print("\n  Error: SERPAPI_KEY not set.")
        print("  export SERPAPI_KEY=your_key_here\n")
        sys.exit(1)

    # Parse --depth
    depth = 20
    if "--depth" in args:
        idx = args.index("--depth")
        if idx + 1 < len(args):
            depth = int(args[idx + 1])
            args = [a for i, a in enumerate(args) if i not in (idx, idx + 1)]

    # Parse --domain
    domain = os.environ.get("TARGET_DOMAIN", "")
    if "--domain" in args:
        idx = args.index("--domain")
        if idx + 1 < len(args):
            domain = args[idx + 1]
            args = [a for i, a in enumerate(args) if i not in (idx, idx + 1)]

    if not domain:
        print("\n  Error: TARGET_DOMAIN not set.")
        print("  export TARGET_DOMAIN=yourdomain.com  or use --domain yourdomain.com\n")
        sys.exit(1)

    # Keywords: CLI arg > seo-keywords.txt
    if args:
        keywords = [" ".join(args)]
    else:
        keywords = load_keywords_from_file()
        if not keywords:
            print("\n  Error: no keywords found.")
            print("  Create seo-keywords.txt (one keyword per line) in your project directory,")
            print("  or pass a keyword as an argument.\n")
            sys.exit(1)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n  SEO Rank Check — {domain}")
    print(f"  {now}  |  checking top {depth} results per keyword")
    print(f"  {len(keywords)} keyword{'s' if len(keywords) != 1 else ''} · "
          f"{len(keywords)} search credit{'s' if len(keywords) != 1 else ''} used")
    print()
    print(DIVIDER)
    print(f"  {'KEYWORD':<34} {'POS':>4}  {'PAGE / URL'}")
    print(DIVIDER)

    found_count = 0
    for i, kw in enumerate(keywords):
        data = search(kw, depth, api_key)
        pos, title, url = find_rank(data, domain)

        if pos:
            found_count += 1
            print(f"  {kw:<34} #{pos:<3}  {shorten_url(url)}")
        else:
            print(f"  {kw:<34}  {'—':>4}  not in top {depth}")

        if i < len(keywords) - 1:
            time.sleep(1)

    print(DIVIDER)
    print(f"\n  {found_count}/{len(keywords)} keywords ranked in top {depth}")
    remaining = credits_remaining(api_key)
    print(f"  SerpApi credits remaining: {remaining}")
    print()


if __name__ == "__main__":
    main()
