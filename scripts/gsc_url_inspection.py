#!/usr/bin/env python3
"""
gsc_url_inspection.py
Check Google Search Console URL Inspection API indexing status for specific pages.

Uses your active gcloud login — no pip dependencies required.

Usage:
    python3 scripts/gsc_url_inspection.py https://www.example.com/ https://www.example.com/page/
    python3 scripts/gsc_url_inspection.py --file urls.txt https://www.example.com/
    python3 scripts/gsc_url_inspection.py --sitemap https://www.example.com/ https://www.example.com/sitemap.xml

Site URL format (in order of precedence):
    1. --sitemap flag  (fetch URLs from sitemap at given URL)
    2. --file flag  (read URLs from newline-delimited file, one per line)
    3. Positional CLI arguments (URLs to inspect)

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
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

DIVIDER = "  " + "─" * 60


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


def inspect_url(inspection_url, site_url, token):
    """Check indexing status of a single URL."""
    url = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
    
    payload = {
        "inspectionUrl": inspection_url,
        "siteUrl": site_url,
        "languageCode": "en-US",
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
        return {"error": f"HTTP {e.code}: {msg}"}
    except Exception as e:
        return {"error": str(e)}


def fetch_sitemap_urls(sitemap_url):
    """Fetch URLs from a sitemap."""
    try:
        with urllib.request.urlopen(sitemap_url, timeout=20) as resp:
            content = resp.read().decode("utf-8")
            root = ET.fromstring(content)
            
            # Handle both sitemap index and sitemap URLs
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = []
            
            # If it's a sitemap index, return sub-sitemaps
            sitemaps = root.findall("sm:sitemap/sm:loc", ns)
            if sitemaps:
                return [sm.text for sm in sitemaps]
            
            # Otherwise, extract URLs
            locs = root.findall("sm:url/sm:loc", ns)
            return [loc.text for loc in locs]
    except Exception as e:
        print(f"\n  Error fetching sitemap: {e}\n")
        return []


def parse_args(args):
    """Parse command-line arguments."""
    opts = {
        "urls": [],
        "file": None,
        "sitemap": None,
    }

    args = list(args)

    if "--file" in args:
        idx = args.index("--file")
        if idx + 1 < len(args):
            opts["file"] = args[idx + 1]
            del args[idx:idx + 2]

    if "--sitemap" in args:
        idx = args.index("--sitemap")
        if idx + 1 < len(args):
            opts["sitemap"] = args[idx + 1]
            del args[idx:idx + 2]

    opts["urls"] = args

    return opts


def main():
    opts = parse_args(sys.argv[1:])

    urls_to_check = []

    # Load URLs from file if specified
    if opts["file"]:
        try:
            with open(opts["file"]) as f:
                urls_to_check = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"\n  Error reading file: {e}\n")
            sys.exit(1)

    # Load URLs from sitemap if specified
    if opts["sitemap"]:
        sitemap_urls = fetch_sitemap_urls(opts["sitemap"])
        urls_to_check.extend(sitemap_urls)

    # Add positional URLs
    urls_to_check.extend(opts["urls"])

    if not urls_to_check:
        print("\n  Error: no URLs provided.")
        print("  Usage: python3 gsc_url_inspection.py <url1> <url2> ...")
        print("         python3 gsc_url_inspection.py --file urls.txt https://www.example.com/")
        print("         python3 gsc_url_inspection.py --sitemap https://www.example.com/sitemap.xml https://www.example.com/\n")
        sys.exit(1)

    # The last URL should be the site URL for the GSC property
    site_url = urls_to_check[-1]
    inspection_urls = urls_to_check[:-1] if len(urls_to_check) > 1 else urls_to_check

    # Get auth token
    token = get_access_token()

    print(f"\n{DIVIDER}")
    print(f"  Checking {len(inspection_urls)} URL(s) for site: {site_url}")
    print(DIVIDER)

    results = {
        "indexed": [],
        "not_indexed": [],
        "errors": [],
    }

    for i, url in enumerate(inspection_urls, 1):
        print(f"  [{i}/{len(inspection_urls)}] {url}...", end=" ", flush=True)
        
        response = inspect_url(url, site_url, token)

        if "error" in response:
            print(f"✗ ERROR")
            results["errors"].append({"url": url, "error": response["error"]})
            continue

        # Check if indexed
        index_status = response.get("inspectionResult", {}).get("indexStatusResult", {})
        coverage_state = index_status.get("coverageState", "UNKNOWN")
        
        if coverage_state in ("INDEXED", "Submitted and indexed"):
            print(f"✓ INDEXED")
            results["indexed"].append(url)
        elif coverage_state == "UNCRAWLED":
            print(f"✗ NOT CRAWLED")
            results["not_indexed"].append({"url": url, "reason": "Not crawled by Google"})
        elif coverage_state == "CRAWLED":
            print(f"⚠ CRAWLED (not indexed)")
            results["not_indexed"].append({"url": url, "reason": "Crawled but not indexed"})
        else:
            print(f"? {coverage_state}")
            results["not_indexed"].append({"url": url, "reason": coverage_state})

    # Summary
    print(f"\n{DIVIDER}")
    print(f"  INDEXED: {len(results['indexed'])}")
    print(f"  NOT INDEXED: {len(results['not_indexed'])}")
    if results["errors"]:
        print(f"  ERRORS: {len(results['errors'])}")
    print(DIVIDER)

    if results["not_indexed"]:
        print(f"\n  Not indexed ({len(results['not_indexed'])}):")
        for item in results["not_indexed"]:
            reason = item.get("reason", "Unknown")
            print(f"    • {item['url']}")
            print(f"      Reason: {reason}")

    if results["errors"]:
        print(f"\n  Errors ({len(results['errors'])}):")
        for item in results["errors"]:
            print(f"    • {item['url']}")
            print(f"      Error: {item['error']}")

    print()


if __name__ == "__main__":
    main()
