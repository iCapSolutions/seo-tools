#!/usr/bin/env python3
"""
_wp_extract_fields.py
Read a WP REST API JSON response from a file and print one or more
dot-separated field paths to stdout (one per line).

Usage:
    python3 _wp_extract_fields.py <json-file> <field> [field ...]

Examples:
    python3 _wp_extract_fields.py /tmp/resp.json id
    python3 _wp_extract_fields.py /tmp/resp.json title.rendered status link
"""
import json, sys

if len(sys.argv) < 3:
    print("Usage: _wp_extract_fields.py <json-file> <field> [field ...]", file=sys.stderr)
    sys.exit(1)

with open(sys.argv[1]) as f:
    d = json.load(f)

# If the API returned an error object, surface it and exit non-zero
if isinstance(d, dict) and 'code' in d:
    print(f"API error: {d.get('code')} — {d.get('message', '')}", file=sys.stderr)
    sys.exit(1)

for field in sys.argv[2:]:
    val = d
    for key in field.split('.'):
        val = val.get(key, '') if isinstance(val, dict) else ''
    print(val)
