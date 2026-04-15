#!/usr/bin/env python3
"""
gsc_search_analytics.py
Query Google Search Console Search Analytics API for traffic data.

Uses your active gcloud login — no pip dependencies required.

Usage:
    python3 scripts/gsc_search_analytics.py https://www.example.com/         # single site
    python3 scripts/gsc_search_analytics.py sc-domain:example.com            # domain property
    python3 scripts/gsc_search_analytics.py --all                            # all known sites
    python3 scripts/gsc_search_analytics.py https://www.example.com/ --by device
    python3 scripts/gsc_search_analytics.py https://www.example.com/ --by country
    python3 scripts/gsc_search_analytics.py https://www.example.com/ --by page
    python3 scripts/gsc_search_analytics.py https://www.example.com/ --by query
    python3 scripts/gsc_search_analytics.py https://www.example.com/ --days 7
    python3 scripts/gsc_search_analytics.py https://www.example.com/ --days 7 --by country --by device

Site URL format (in order of precedence):
    1. --all flag  (queries all entries in KNOWN_SITES)
    2. Positional CLI argument (https://www.example.com/ or sc-domain:example.com)
    3. GSC_SITE_URL env var

    URL-prefix properties: https://www.example.com/, https://example.com/
    Domain properties: sc-domain:example.com

Auth:
    Requires gcloud CLI, authenticated via:
        gcloud auth login                                     # personal/user account
        gcloud auth activate-service-account --key-file=...  # service account

Dimensions:
    country       — Country of search (ISO 3166-1 alpha-3)
    device        — Device category (DESKTOP, MOBILE, TABLET)
    page          — Landing page / canonical URL
    query         — Search query
    searchAppearance — Rich result type (AMP, Snippet, FAQ, etc.)

Date range:
    Default: last 90 days
    Use --days N to query last N days (max 16 months back)

Requires: gcloud CLI installed and authenticated
"""

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

DIVIDER = "  " + "─" * 60

# Known Search Console properties — add new sites here
# Format: "display_name": "site_url"
# URL-prefix: https://www.example.com/
# Domain: sc-domain:example.com
KNOWN_SITES = {
    "icapsolutions.com":    "https://www.icapsolutions.com/",
    "glamourpuss.com":      "https://www.glamourpuss.com/",
    "happyhourcircuit.com": "https://www.happyhourcircuit.com/",
    "numbercrate.com":      "https://www.numbercrate.com/",
    "mailaddiction.com":    "https://www.mailaddiction.com/",
    "madkrab.com":          "https://www.madkrab.com/",
}

DIMENSION_NAMES = {
    "country",
    "device",
    "page",
    "query",
    "searchAppearance",
}


def get_access_token():
    """Get OAuth access token for Search Console API."""
    # 1. Direct token override (useful for testing or CI)
    token = os.environ.get("GSC_ACCESS_TOKEN", "")
    if token:
        return token

    # 2. Service account JSON via google-auth (pip install google-auth)
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if sa_path:
        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests
            scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
            creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
            creds.refresh(google.auth.transport.requests.Request())
            return creds.token
        except ImportError:
            print("\n  Warning: GOOGLE_APPLICATION_CREDENTIALS set but google-auth not installed.")
            print("  pip install google-auth  — or use GSC_ACCESS_TOKEN instead.\n")
        except Exception as e:
            print(f"\n  Error loading service account: {e}\n")
            sys.exit(1)

    # 3. gcloud CLI
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token",
             "--scopes=https://www.googleapis.com/auth/webmasters.readonly"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"\n  Error: gcloud auth failed — {e.stderr.strip()}")
        print("  Run: gcloud auth login\n")
        sys.exit(1)
    except FileNotFoundError:
        pass

    print("\n  Error: no authentication method found.")
    print("  Options (in order of preference):")
    print("    1. Set GSC_ACCESS_TOKEN=<token>  (get one from https://developers.google.com/oauthplayground)")
    print("       Scope: https://www.googleapis.com/auth/webmasters.readonly")
    print("    2. Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json  +  pip install google-auth")
    print("    3. Install gcloud: https://cloud.google.com/sdk/docs/install  then: gcloud auth login\n")
    sys.exit(1)


def query_search_analytics(site_url, token, start_date, end_date, dimensions=None, row_limit=25000):
    """Query Search Console Search Analytics API."""
    if dimensions is None:
        dimensions = []

    url = (
        "https://www.googleapis.com/webmasters/v3/sites/"
        + urllib.parse.quote(site_url, safe="")
        + "/searchAnalytics/query"
    )

    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": row_limit,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            msg = body
        print(f"\n  HTTP {e.code}: {msg}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n  Request error: {e}\n")
        sys.exit(1)


def format_table(rows, dimensions, totals_row=None):
    """Format rows as a human-readable table."""
    if not rows and not totals_row:
        return "  (no data)"

    # Headers: dimensions + metrics
    headers = list(dimensions) + ["Clicks", "Impressions", "CTR", "Position"]

    # Determine column widths
    widths = {h: len(h) for h in headers}
    for row in rows:
        for i, dim in enumerate(dimensions):
            val = str(row.get("keys", [""] * len(dimensions))[i])
            widths[dim] = max(widths[dim], len(val))
        # Metrics are small and right-aligned
        widths["Clicks"] = max(widths["Clicks"], 8)
        widths["Impressions"] = max(widths["Impressions"], 12)
        widths["CTR"] = max(widths["CTR"], 8)
        widths["Position"] = max(widths["Position"], 10)

    # Print header
    header_line = "  " + " | ".join(h.ljust(widths[h]) for h in headers)
    print(header_line)
    print("  " + "-" * (len(header_line) - 2))

    # Print rows
    for row in rows:
        cells = []
        for i, dim in enumerate(dimensions):
            val = str(row.get("keys", [""] * len(dimensions))[i])
            cells.append(val.ljust(widths[dim]))
        clicks = row.get("clicks", 0)
        impressions = row.get("impressions", 0)
        ctr = row.get("ctr", 0)
        position = row.get("position", 0)
        cells.append(f"{int(clicks)}".rjust(widths["Clicks"]))
        cells.append(f"{int(impressions)}".rjust(widths["Impressions"]))
        cells.append(f"{ctr:.1%}".rjust(widths["CTR"]))
        cells.append(f"{position:.2f}".rjust(widths["Position"]))
        print("  " + " | ".join(cells))

    # Print totals row if provided
    if totals_row:
        print("  " + "-" * (len(header_line) - 2))
        cells = ["TOTAL".ljust(widths[dimensions[0]]) if dimensions else ""]
        cells += ["".ljust(widths[d]) for d in dimensions[1:]] if len(dimensions) > 1 else []
        total_clicks = totals_row.get("total_clicks", 0)
        total_impressions = totals_row.get("total_impressions", 0)
        total_ctr = totals_row.get("total_ctr", 0)
        total_position = totals_row.get("total_position", 0)
        cells.append(f"{int(total_clicks)}".rjust(widths["Clicks"]))
        cells.append(f"{int(total_impressions)}".rjust(widths["Impressions"]))
        cells.append(f"{total_ctr:.1%}".rjust(widths["CTR"]))
        cells.append(f"{total_position:.2f}".rjust(widths["Position"]))
        print("  " + " | ".join(cells))


def shorten(s, max_len=50):
    """Shorten string with ellipsis if too long."""
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def parse_args(args):
    """Parse command-line arguments."""
    opts = {
        "all": False,
        "site_url": None,
        "dimensions": [],
        "days": 90,
    }

    args = list(args)

    if "--all" in args:
        opts["all"] = True
        args.remove("--all")

    if "--days" in args:
        idx = args.index("--days")
        if idx + 1 < len(args):
            opts["days"] = int(args[idx + 1])
            del args[idx:idx + 2]

    # Handle multiple --by dimensions
    while "--by" in args:
        idx = args.index("--by")
        if idx + 1 < len(args):
            dim = args[idx + 1]
            if dim in DIMENSION_NAMES:
                opts["dimensions"].append(dim)
            del args[idx:idx + 2]
        else:
            break

    # Remaining positional arg is the site URL
    if args:
        opts["site_url"] = args[0]

    return opts


def main():
    opts = parse_args(sys.argv[1:])

    # Determine site(s) to query
    sites = {}
    if opts["all"]:
        sites = KNOWN_SITES
    else:
        site_url = opts["site_url"] or os.environ.get("GSC_SITE_URL")
        if not site_url:
            print("\n  Error: no site URL provided.")
            print("  Usage: python3 gsc_search_analytics.py <site_url>")
            print("         python3 gsc_search_analytics.py --all")
            print("         export GSC_SITE_URL=https://www.example.com/\n")
            sys.exit(1)
        sites = {"current": site_url}

    # Get auth token
    token = get_access_token()

    # Calculate date range
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=opts["days"] - 1)
    date_range_str = f"{start_date} to {end_date}"

    # Default dimensions if none specified
    if not opts["dimensions"]:
        opts["dimensions"] = ["query"]

    # Query each site
    for name, site_url in sites.items():
        print(f"\n{DIVIDER}")
        print(f"  {name}: {shorten(site_url)}")
        print(f"  {date_range_str}")
        print(f"  Grouped by: {', '.join(opts['dimensions'])}")
        print(DIVIDER)

        try:
            response = query_search_analytics(
                site_url,
                token,
                start_date.isoformat(),
                end_date.isoformat(),
                dimensions=opts["dimensions"]
            )
        except Exception as e:
            print(f"  Error querying {name}: {e}")
            continue

        rows = response.get("rows", [])
        if not rows:
            print("  (no data)")
            continue

        # Compute totals
        total_clicks = sum(r.get("clicks", 0) for r in rows)
        total_impressions = sum(r.get("impressions", 0) for r in rows)
        total_ctr = total_clicks / total_impressions if total_impressions > 0 else 0
        total_position = (
            sum(r.get("position", 0) * r.get("impressions", 1) for r in rows) / total_impressions
            if total_impressions > 0 else 0
        )
        totals_row = {
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "total_ctr": total_ctr,
            "total_position": total_position,
        }

        format_table(rows, opts["dimensions"], totals_row)
        print()

    print()


if __name__ == "__main__":
    main()
