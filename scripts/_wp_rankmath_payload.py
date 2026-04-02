#!/usr/bin/env python3
"""
Build a Rank Math updateMeta payload.
Usage: python3 _wp_rankmath_payload.py <meta-desc> <focus-kw> <object-id> [object-type]
Prints JSON to stdout.
"""
import json, sys

meta_desc  = sys.argv[1] if len(sys.argv) > 1 else ''
focus_kw   = sys.argv[2] if len(sys.argv) > 2 else ''
object_id  = int(sys.argv[3]) if len(sys.argv) > 3 else 0
object_type = sys.argv[4] if len(sys.argv) > 4 else 'post'

m = {}
if meta_desc: m['rank_math_description']   = meta_desc
if focus_kw:  m['rank_math_focus_keyword'] = focus_kw

payload = {'objectType': object_type, 'objectID': object_id, 'meta': m}
print(json.dumps(payload))
