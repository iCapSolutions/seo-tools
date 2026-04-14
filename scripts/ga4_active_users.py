#!/usr/bin/env python3
"""
ga4_active_users.py
Query the GA4 Realtime API for active users on a website.

Uses your active gcloud login — no pip dependencies required.

Usage:
    python3 scripts/ga4_active_users.py                      # last 30 min, default property
    python3 scripts/ga4_active_users.py 123456789            # specific property ID
    python3 scripts/ga4_active_users.py --all                # all known properties, summary table
    python3 scripts/ga4_active_users.py --minutes 5          # narrow the window (e.g. "right now")
    python3 scripts/ga4_active_users.py --breakdown          # per-minute count breakdown
    python3 scripts/ga4_active_users.py --by country         # breakdown by country
    python3 scripts/ga4_active_users.py --by page            # breakdown by page/screen
    python3 scripts/ga4_active_users.py --by device          # breakdown by device category
    python3 scripts/ga4_active_users.py --by city            # breakdown by city

Property ID (in order of precedence):
    1. --all flag  (queries all entries in KNOWN_PROPERTIES)
    2. Positional CLI argument
    3. GA4_PROPERTY_ID env var

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

# Known GA4 properties — add new sites here as you grant access.
# Format: "display_name": "property_id"
KNOWN_PROPERTIES = {
    "icapsolutions.com":    "309879063",
    "glamourpuss.com":      "397152726",
    "happyhourcircuit.com": "528520331",
    "numbercrate.com":      "532631310",
}

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
            ["gcloud", "auth", "print-access-token",
             "--scopes=https://www.googleapis.com/auth/analytics.readonly"],
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


def run_realtime_report(property_id, token, start_minutes_ago=29, dimensions=None, silent=False):
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
        if silent:
            return None
        print(f"\n  HTTP {e.code}: {msg}\n")
        sys.exit(1)
    except Exception as e:
        if silent:
            return None
        print(f"\n  Request error: {e}\n")
        sys.exit(1)


def get_total(response):
    totals = response.get("totals", [])
    if totals and totals[0].get("metricValues"):
        return int(totals[0]["metricValues"][0]["value"])
    # Fall back to summing rows (also handles zero-result case)
    rows = response.get("rows", [])
    if not rows:
        return 0
    return sum(int(r["metricValues"][0]["value"]) for r in rows)


def shorten(s, max_len=40):
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def parse_args(args):
    opts = {
        "all":       False,
        "breakdown": False,
        "by_dim":    None,
        "minutes":   30,
        "property":  None,
    }

    args = list(args)

    if "--all" in args:
        opts["all"] = True
        args.remove("--all")

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

    if opts["by_dim"] and opts["by_dim"] not in DIM_MAP:
        print(f"\n  Error: unknown dimension '{opts['by_dim']}'.")
        print(f"  Options: {', '.join(DIM_MAP)}\n")
        sys.exit(1)

    start_minutes_ago = opts["minutes"] - 1  # API is 0-indexed (0 = current minute)
    window = opts["minutes"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    token = get_access_token()

    # ── All-properties summary ──────────────────────────────────────────────
    if opts["all"]:
        print(f"\n  GA4 Realtime — all properties")
        print(f"  {now}  |  last {window} minute{'s' if window != 1 else ''}")
        print()
        print(DIVIDER)
        print(f"  {'SITE':<28} {'PROPERTY ID':>12}  {'ACTIVE USERS':>12}")
        print(DIVIDER)
        grand_total = 0
        for name, pid in KNOWN_PROPERTIES.items():
            resp = run_realtime_report(pid, token, start_minutes_ago, silent=True)
            if resp is None:
                print(f"  {shorten(name, 28):<28} {pid:>12}  {'ERROR':>12}")
            else:
                count = get_total(resp)
                grand_total += count
                print(f"  {shorten(name, 28):<28} {pid:>12}  {count:>12}")
        print(DIVIDER)
        print(f"  {'TOTAL':<28} {'':>12}  {grand_total:>12}")
        print()
        return grand_total

    # ── Single-property mode ────────────────────────────────────────────────
    property_id = opts["property"] or os.environ.get("GA4_PROPERTY_ID", "")
    if not property_id:
        print("\n  Error: GA4 property ID required.")
        print("  Pass as argument, set GA4_PROPERTY_ID, or use --all")
        print("  Find it in: GA4 → Admin → Property Settings → Property ID\n")
        sys.exit(1)

    dimensions = []
    if opts["breakdown"]:
        dimensions = ["minutesAgo"]
    elif opts["by_dim"]:
        dimensions = [DIM_MAP[opts["by_dim"]]]

    response = run_realtime_report(property_id, token, start_minutes_ago, dimensions or None)
    total = get_total(response)

    # Resolve display name if it's a known property
    name_map = {v: k for k, v in KNOWN_PROPERTIES.items()}
    display = name_map.get(property_id, f"property {property_id}")

    print(f"\n  GA4 Realtime — {display}")
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
