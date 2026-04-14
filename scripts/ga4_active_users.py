#!/usr/bin/env python3
"""
ga4_active_users.py
Query the GA4 Realtime API for active users on a website.

Uses your active gcloud login — no pip dependencies required.

Usage:
    python3 scripts/ga4_active_users.py                      # last 30 min, default property
    python3 scripts/ga4_active_users.py 123456789            # specific property ID
    python3 scripts/ga4_active_users.py --minutes 5          # narrow the window (e.g. "right now")
    python3 scripts/ga4_active_users.py --breakdown          # per-minute count breakdown
    python3 scripts/ga4_active_users.py --by country         # breakdown by country
    python3 scripts/ga4_active_users.py --by page            # breakdown by page/screen
    python3 scripts/ga4_active_users.py --by device          # breakdown by device category
    python3 scripts/ga4_active_users.py --by city            # breakdown by city

Property ID (in order of precedence):
    1. Positional CLI argument
    2. GA4_PROPERTY_ID env var

    Find your Property ID in GA4 → Admin → Property Settings → Property ID.

Auth:
    Requires gcloud CLI, authenticated via:
        gcloud auth login                                     # personal/user account
        gcloud auth activate-service-account --key-file=...  # service account

Requires: gcloud CLI installed and authenticated
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

DIVIDER = "  " + "─" * 60

DIM_MAP = {
    "country":  "country",
    "page":     "unifiedScreenName",
    "device":   "deviceCategory",
    "city":     "city",
    "platform": "platform",
}


def get_access_token():
    # 1. Direct token override (useful for testing or CI)
    token = os.environ.get("GA4_ACCESS_TOKEN", "")
    if token:
        return token

    # 2. Service account JSON via google-auth (pip install google-auth)
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if sa_path:
        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests
            scopes = ["https://www.googleapis.com/auth/analytics.readonly"]
            creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
            creds.refresh(google.auth.transport.requests.Request())
            return creds.token
        except ImportError:
            print("\n  Warning: GOOGLE_APPLICATION_CREDENTIALS set but google-auth not installed.")
            print("  pip install google-auth  — or use GA4_ACCESS_TOKEN instead.\n")
        except Exception as e:
            print(f"\n  Error loading service account: {e}\n")
            sys.exit(1)

    # 3. gcloud CLI
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
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
    print("    1. Set GA4_ACCESS_TOKEN=<token>  (get one from https://developers.google.com/oauthplayground)")
    print("       Scope: https://www.googleapis.com/auth/analytics.readonly")
    print("    2. Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json  +  pip install google-auth")
    print("    3. Install gcloud: https://cloud.google.com/sdk/docs/install  then: gcloud auth login\n")
    sys.exit(1)


def run_realtime_report(property_id, token, start_minutes_ago=29, dimensions=None):
    url = (
        "https://analyticsdata.googleapis.com/v1beta"
        f"/properties/{property_id}:runRealtimeReport"
    )
    payload = {
        "metrics": [{"name": "activeUsers"}],
        "minuteRanges": [{"startMinutesAgo": start_minutes_ago, "endMinutesAgo": 0}],
        "metricAggregations": ["TOTAL"],
    }
    if dimensions:
        payload["dimensions"] = [{"name": d} for d in dimensions]

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


def get_total(response):
    totals = response.get("totals", [])
    if totals:
        return int(totals[0]["metricValues"][0]["value"])
    return sum(int(r["metricValues"][0]["value"]) for r in response.get("rows", []))


def shorten(s, max_len=40):
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def parse_args(args):
    opts = {
        "breakdown": False,
        "by_dim":    None,
        "minutes":   30,
        "property":  None,
    }

    args = list(args)

    if "--breakdown" in args:
        opts["breakdown"] = True
        args.remove("--breakdown")

    if "--by" in args:
        idx = args.index("--by")
        if idx + 1 < len(args):
            opts["by_dim"] = args[idx + 1]
            del args[idx:idx + 2]

    if "--minutes" in args:
        idx = args.index("--minutes")
        if idx + 1 < len(args):
            opts["minutes"] = int(args[idx + 1])
            del args[idx:idx + 2]

    if args:
        opts["property"] = args[0]

    return opts


def main():
    opts = parse_args(sys.argv[1:])

    property_id = opts["property"] or os.environ.get("GA4_PROPERTY_ID", "")
    if not property_id:
        print("\n  Error: GA4 property ID required.")
        print("  Pass as argument or: export GA4_PROPERTY_ID=your_property_id")
        print("  Find it in: GA4 → Admin → Property Settings → Property ID\n")
        sys.exit(1)

    if opts["by_dim"] and opts["by_dim"] not in DIM_MAP:
        print(f"\n  Error: unknown dimension '{opts['by_dim']}'.")
        print(f"  Options: {', '.join(DIM_MAP)}\n")
        sys.exit(1)

    start_minutes_ago = opts["minutes"] - 1  # API is 0-indexed (0 = current minute)
    window = opts["minutes"]

    dimensions = []
    if opts["breakdown"]:
        dimensions = ["minutesAgo"]
    elif opts["by_dim"]:
        dimensions = [DIM_MAP[opts["by_dim"]]]

    token = get_access_token()
    response = run_realtime_report(property_id, token, start_minutes_ago, dimensions or None)
    total = get_total(response)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n  GA4 Realtime — property {property_id}")
    print(f"  {now}  |  last {window} minute{'s' if window != 1 else ''}")
    print()
    print(DIVIDER)

    if opts["breakdown"]:
        print(f"  {'MINUTES AGO':<18} {'ACTIVE USERS':>12}")
        print(DIVIDER)
        rows = sorted(
            response.get("rows", []),
            key=lambda r: int(r["dimensionValues"][0]["value"])
        )
        for row in rows:
            mins = row["dimensionValues"][0]["value"]
            users = row["metricValues"][0]["value"]
            label = f"{mins} min ago"
            print(f"  {label:<18} {users:>12}")
        print(DIVIDER)
        print(f"  {'TOTAL':<18} {total:>12}")

    elif opts["by_dim"]:
        label = opts["by_dim"].upper()
        print(f"  {label:<40} {'ACTIVE USERS':>12}")
        print(DIVIDER)
        rows = sorted(
            response.get("rows", []),
            key=lambda r: int(r["metricValues"][0]["value"]),
            reverse=True
        )
        for row in rows:
            dim_val = row["dimensionValues"][0]["value"]
            users = row["metricValues"][0]["value"]
            print(f"  {shorten(dim_val):<40} {users:>12}")
        print(DIVIDER)
        print(f"  {'TOTAL':<40} {total:>12}")

    else:
        print(f"  Active users:  {total}")
        print(DIVIDER)

    print()
    return total


if __name__ == "__main__":
    main()
