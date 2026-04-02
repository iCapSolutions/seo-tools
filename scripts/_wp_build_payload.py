#!/usr/bin/env python3
"""
Build a WordPress REST API page update payload.
Usage: python3 _wp_build_payload.py <html-file> <status> <title> <meta-desc> <focus-kw> <groomed-at> <featured-media> <slug>
Prints JSON to stdout.
"""
import json, sys

html_file     = sys.argv[1]
status        = sys.argv[2]
title         = sys.argv[3] if len(sys.argv) > 3 else ''
meta_desc     = sys.argv[4] if len(sys.argv) > 4 else ''
focus_kw      = sys.argv[5] if len(sys.argv) > 5 else ''
groomed_at    = sys.argv[6] if len(sys.argv) > 6 else ''
featured_media = sys.argv[7] if len(sys.argv) > 7 else ''
slug          = sys.argv[8] if len(sys.argv) > 8 else ''

with open(html_file) as f:
    content = f.read()

payload = {'content': content, 'status': status}
if title:          payload['title']          = title
if featured_media: payload['featured_media'] = int(featured_media)
if slug:           payload['slug']           = slug

meta = {'_oz_groomed_by': 'Oz (Warp)', '_oz_groomed_at': groomed_at}
payload['meta'] = meta

print(json.dumps(payload))
