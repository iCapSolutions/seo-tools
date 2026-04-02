#!/usr/bin/env python3
"""
Read a WordPress REST API page JSON from stdin and print a clean summary.
Handles both single-object and array responses.
"""
import json, sys, re
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    def handle_data(self, d):
        self.text.append(d)
    def get(self):
        return re.sub(r'\n{3,}', '\n\n', ''.join(self.text)).strip()

d = json.load(sys.stdin)
p = d if isinstance(d, dict) else d[0]

rendered = p.get('content', {}).get('rendered', '')
meta    = p.get('meta', {})

# Extract plain text
extractor = TextExtractor()
extractor.feed(rendered)
plain_text = extractor.get()

# Extract all links
links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', rendered)

print()
print('  ID:       ' + str(p.get('id', '')))
print('  Title:    ' + p.get('title', {}).get('rendered', ''))
print('  Status:   ' + p.get('status', ''))
print('  Link:     ' + p.get('link', ''))
print('  Modified: ' + p.get('modified', '')[:10])
seo_desc = meta.get('rank_math_description') or '(set via Rank Math — verify in WP Admin)'
focus_kw = meta.get('rank_math_focus_keyword') or '(set via Rank Math — verify in WP Admin)'
print('  SEO Desc: ' + (seo_desc[:100] if 'Rank Math' not in seo_desc else seo_desc))
print('  Focus KW: ' + focus_kw)

if links:
    print()
    print('  Links in content:')
    for href, text in links:
        is_external = href.startswith('http') and 'icapsolutions.com' not in href
        tag = '(external)' if is_external else '(internal)'
        clean_text = re.sub('<[^>]+>', '', text).strip()
        print(f'    {tag} "{clean_text}" -> {href}')

# Extract images
images = re.findall(r'<img[^>]+>', rendered)
if images:
    print()
    print('  Images in content:')
    for img in images:
        src   = (re.search(r'src=["\']([^"\']+)', img) or re.search(r'', '')).group(1) if re.search(r'src=["\']([^"\']+)', img) else '?'
        alt   = re.search(r'alt=["\']([^"\']*)', img)
        alt   = alt.group(1) if alt else '(no alt)'
        cls   = re.search(r'class=["\']([^"\']+)', img)
        cls   = cls.group(1) if cls else ''
        wp_id = re.search(r'wp-image-(\d+)', cls)
        wp_id = f'wp-id:{wp_id.group(1)}' if wp_id else ''
        alt_warn = ' ⚠ empty alt' if alt in ('', '(no alt)') else ''
        print(f'    {wp_id} src={src.split("/")[-1]} alt="{alt}"{alt_warn}')
else:
    print('  Images in content: (none)')

print()
print('-' * 60)
print(plain_text)
print('-' * 60)
print()
