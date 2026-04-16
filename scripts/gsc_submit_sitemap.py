#!/usr/bin/env python3
"""
gsc_submit_sitemap.py
Submit sitemaps to Google Search Console for crawling and indexing.

Uses your active gcloud login — no pip dependencies required.

Usage:
    python3 scripts/gsc_submit_sitemap.py https://www.example.com/sitemap.xml https://www.example.com/
    python3 scripts/gsc_submit_sitemap.py https://www.example.com/sitemap_index.xml https://www.example.com/

Site URL format:
    The last positional argument is the GSC site URL (property).
    All other arguments are sitemap URLs to submit.

Auth:
    Requires gcloud CLI, authenticated via:
        gcloud auth login                                     # personal/user account
        gcloud auth activate-service-account --key-file=...  # service account

Note: The service account must have Owner or Full access to the Search Console property.

Requires: gcloud CLI installed and authenticated
"""

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import urllib.error

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
            scopes = ["https://www.googleapis.com/auth/webmasters"]
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
             "--scopes=https://www.googleapis.com/auth/webmasters"],
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
    print("       Scope: https://www.googleapis.com/auth/webmasters")
    print("    2. Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json  +  pip install google-auth")
    print("    3. Install gcloud: https://cloud.google.com/sdk/docs/install  then: gcloud auth login\n")
    sys.exit(1)


def submit_sitemap(sitemap_url, site_url, token):
    """Submit a sitemap to Google Search Console."""
    # Encode the sitemap path
    sitemap_path = urllib.parse.quote(sitemap_url, safe="")
    
    url = (
        "https://www.googleapis.com/webmasters/v3/sites/"
        + urllib.parse.quote(site_url, safe="")
        + f"/sitemaps/{sitemap_path}"
    )

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="PUT"
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            # Sitemap submissions may return empty 200 response
            response = json.loads(body) if body else {}
            return {"status": "success", "response": response}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            msg = body
        return {"status": "error", "code": e.code, "message": msg}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main():
    if len(sys.argv) < 3:
        print("\n  Error: missing required arguments.")
        print("  Usage: python3 gsc_submit_sitemap.py <sitemap_url> [<sitemap_url> ...] <site_url>\n")
        print("  Example:")
        print("    python3 gsc_submit_sitemap.py https://www.example.com/sitemap.xml https://www.example.com/\n")
        sys.exit(1)

    # Last argument is the site URL
    site_url = sys.argv[-1]
    sitemap_urls = sys.argv[1:-1]

    # Get auth token
    token = get_access_token()

    print(f"\n{DIVIDER}")
    print(f"  Submitting {len(sitemap_urls)} sitemap(s) to: {site_url}")
    print(DIVIDER)

    results = {
        "success": [],
        "failed": [],
    }

    for i, sitemap_url in enumerate(sitemap_urls, 1):
        print(f"  [{i}/{len(sitemap_urls)}] {sitemap_url}...", end=" ", flush=True)

        response = submit_sitemap(sitemap_url, site_url, token)

        if response["status"] == "success":
            print(f"✓ SUBMITTED")
            results["success"].append(sitemap_url)
        else:
            print(f"✗ FAILED")
            results["failed"].append({
                "url": sitemap_url,
                "code": response.get("code", ""),
                "message": response.get("message", "Unknown error")
            })

    # Summary
    print(f"\n{DIVIDER}")
    print(f"  SUBMITTED: {len(results['success'])}")
    if results["failed"]:
        print(f"  FAILED: {len(results['failed'])}")
    print(DIVIDER)

    if results["failed"]:
        print(f"\n  Failed submissions ({len(results['failed'])}):")
        for item in results["failed"]:
            print(f"    • {item['url']}")
            if item["code"]:
                print(f"      HTTP {item['code']}: {item['message']}")
            else:
                print(f"      Error: {item['message']}")

    print()


if __name__ == "__main__":
    main()
