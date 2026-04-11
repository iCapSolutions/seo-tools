#!/usr/bin/env python3
"""
audit_html_seo.py
Audit HTML files for common SEO issues.

Platform-agnostic — works with WordPress exports, Perl/mod_perl templates,
static HTML, SHTML, or any other HTML file. Does not require a CMS or API.

Usage:
    python3 scripts/audit_html_seo.py templates/home.html
    python3 scripts/audit_html_seo.py templates/            # all .html/.shtml in dir
    python3 scripts/audit_html_seo.py f1.html f2.shtml      # multiple files
    python3 scripts/audit_html_seo.py --live https://example.com/

Exit code: 0 if no ERR-level issues, 1 if any ERR found.

Checks performed:
    <head>
        [ERR]  Missing <title>
        [WARN] Title too short (<10) or too long (>70 chars)
        [ERR]  Missing <meta name="description">
        [WARN] Description too short (<120) or too long (>160 chars)
        [ERR]  Missing <meta name="viewport">
        [WARN] Missing <link rel="canonical">
        [WARN] Missing og:title, og:description, og:image, og:type, og:url
        [INFO] Missing twitter:card, twitter:title, twitter:description
        [WARN] Missing lang attribute on <html>

    <body>
        [ERR]  No <h1> found
        [WARN] Multiple <h1> tags
        [WARN] No <h2> found
        [WARN] Heading level skipped (e.g. h1 → h3)
        [WARN] Missing <main> landmark
        [ERR]  <img> missing alt attribute entirely
        [WARN] <img> with empty alt attribute (only ok for decorative images)
        [INFO] <input> (text/email/password) with no <label> or aria-label

    General
        [INFO] Server-side includes detected (SSI/TMPL) — some content may be in included files
"""

import sys
import os
import re
import html.parser
import urllib.request
import urllib.error
from pathlib import Path


# ── Terminal colours ──────────────────────────────────────────────────────────

RESET  = '\033[0m'
BOLD   = '\033[1m'
RED    = '\033[91m'
YELLOW = '\033[93m'
CYAN   = '\033[96m'
GREEN  = '\033[92m'
DIM    = '\033[2m'
DIVIDER = '  ' + '─' * 68


def col(text, code): return f'{code}{text}{RESET}'


# ── HTML parser ───────────────────────────────────────────────────────────────

class SEOParser(html.parser.HTMLParser):

    def __init__(self):
        super().__init__()
        self.html_lang    = None   # lang attr on <html>
        self.title        = None   # text content of <title>
        self.meta         = {}     # name/property (lowercased) → content
        self.canonical    = None   # href of <link rel="canonical">
        self.has_main     = False
        self.headings     = []     # list of (level:int, text:str)
        self.images       = []     # list of {'src': str, 'alt': str|None}
        self.inputs       = []     # list of {'type', 'id', 'name', 'aria_label'}
        self.label_fors   = set()  # all `for` values from <label> elements
        self.includes     = []     # (kind, filename) for SSI/TMPL includes

        self._in_title    = False
        self._in_heading  = None   # current heading tag e.g. 'h1'
        self._buf         = ''     # text buffer for current element

    # ── Comments (SSI / TMPL includes) ────────────────────────────────────────

    def handle_comment(self, data):
        data = data.strip()
        # Apache SSI: <!--#include file="header.html" -->
        m = re.search(r'#include\s+(?:file|virtual)=["\']([^"\']+)', data)
        if m:
            self.includes.append(('SSI', m.group(1)))
            return
        # HTML::Template: <!--TMPL_INCLUDE NAME="header.html"-->
        m = re.search(r'TMPL_INCLUDE\s+NAME=["\']([^"\']+)', data)
        if m:
            self.includes.append(('TMPL', m.group(1)))

    # ── Start tags ────────────────────────────────────────────────────────────

    def handle_starttag(self, tag, attrs):
        tag   = tag.lower()
        attrs = dict((k.lower(), v or '') for k, v in attrs)

        if tag == 'html':
            self.html_lang = attrs.get('lang')

        elif tag == 'title':
            self._in_title = True
            self._buf = ''

        elif tag == 'meta':
            name    = attrs.get('name', '').lower().strip()
            prop    = attrs.get('property', '').lower().strip()
            content = attrs.get('content', '')
            if name:
                self.meta[name] = content
            if prop:
                self.meta[prop] = content

        elif tag == 'link':
            if attrs.get('rel', '').lower() == 'canonical':
                self.canonical = attrs.get('href', '')

        elif tag == 'main':
            self.has_main = True

        elif re.match(r'^h[1-6]$', tag):
            self._in_heading = tag
            self._buf = ''

        elif tag == 'img':
            # alt is None if attribute absent, '' if present but empty
            alt = attrs.get('alt') if 'alt' in attrs else None
            self.images.append({'src': attrs.get('src', ''), 'alt': alt})

        elif tag == 'input':
            itype = attrs.get('type', 'text').lower()
            if itype in ('text', 'email', 'password', 'search', 'tel', 'url', 'number'):
                self.inputs.append({
                    'type':       itype,
                    'id':         attrs.get('id', ''),
                    'name':       attrs.get('name', ''),
                    'aria_label': attrs.get('aria-label', ''),
                })

        elif tag == 'label':
            if attrs.get('for'):
                self.label_fors.add(attrs['for'])

    # ── End tags ──────────────────────────────────────────────────────────────

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'title':
            self.title = self._buf.strip()
            self._in_title = False
        elif self._in_heading and tag == self._in_heading:
            level = int(self._in_heading[1])
            self.headings.append((level, self._buf.strip()))
            self._in_heading = None

    # ── Text ──────────────────────────────────────────────────────────────────

    def handle_data(self, data):
        if self._in_title or self._in_heading:
            self._buf += data


# ── Audit logic ───────────────────────────────────────────────────────────────

def audit(source_label, html_text):
    """Parse html_text and return list of (severity, message) tuples."""

    parser = SEOParser()
    # Strip script/style content so their text doesn't pollute heading reads
    html_text_clean = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
    html_text_clean = re.sub(r'<style[^>]*>.*?</style>',  '', html_text_clean, flags=re.DOTALL | re.IGNORECASE)
    try:
        parser.feed(html_text_clean)
    except Exception:
        pass  # keep going even with malformed HTML

    issues = []  # (severity, message)

    def e(msg):  issues.append(('ERR',  msg))
    def w(msg):  issues.append(('WARN', msg))
    def i(msg):  issues.append(('INFO', msg))

    includes_present = bool(parser.includes)

    # ── <html lang> ───────────────────────────────────────────────────────────
    if not parser.html_lang:
        w('Missing lang attribute on <html> (e.g. <html lang="en">)')

    # ── <title> ───────────────────────────────────────────────────────────────
    if not parser.title:
        e('Missing <title> tag')
    else:
        tlen = len(parser.title)
        i(f'Title ({tlen} chars): "{parser.title}"')
        if tlen < 10:
            w(f'Title too short ({tlen} chars) — aim for 30–70')
        elif tlen > 70:
            w(f'Title too long ({tlen} chars) — keep under 70 to avoid truncation in SERPs')

    # ── Meta description ──────────────────────────────────────────────────────
    desc = parser.meta.get('description')
    if desc is None:
        e('Missing <meta name="description">')
    else:
        dlen = len(desc)
        i(f'Description ({dlen} chars): "{desc[:80]}{"…" if dlen > 80 else ""}"')
        if dlen < 120:
            w(f'Meta description too short ({dlen} chars) — aim for 120–160')
        elif dlen > 160:
            w(f'Meta description too long ({dlen} chars) — may be truncated in SERPs')

    # ── Viewport ──────────────────────────────────────────────────────────────
    if 'viewport' not in parser.meta:
        e('Missing <meta name="viewport"> — critical for mobile ranking')
    else:
        i(f'Viewport: {parser.meta["viewport"]}')

    # ── Canonical ─────────────────────────────────────────────────────────────
    if parser.canonical is None:
        w('Missing <link rel="canonical"> — helps prevent duplicate content issues')
    else:
        i(f'Canonical: {parser.canonical}')

    # ── Open Graph ────────────────────────────────────────────────────────────
    og_required = ['og:title', 'og:description', 'og:image', 'og:type', 'og:url']
    og_missing  = [tag for tag in og_required if tag not in parser.meta]
    if og_missing:
        w(f'Missing Open Graph tags: {", ".join(og_missing)}')
    else:
        i('Open Graph: all required tags present')

    # ── Twitter Card ──────────────────────────────────────────────────────────
    tw_required = ['twitter:card', 'twitter:title', 'twitter:description']
    tw_missing  = [tag for tag in tw_required if tag not in parser.meta]
    if tw_missing:
        i(f'Missing Twitter Card tags: {", ".join(tw_missing)}')

    # ── Headings ─────────────────────────────────────────────────────────────
    h1s = [t for l, t in parser.headings if l == 1]
    h2s = [t for l, t in parser.headings if l == 2]

    if not h1s:
        if includes_present:
            w('No <h1> found in this file — may be in an included file (check includes)')
        else:
            e('No <h1> found — every page should have exactly one <h1>')
    elif len(h1s) > 1:
        w(f'Multiple <h1> tags ({len(h1s)}) — use only one per page')
        for t in h1s:
            i(f'  h1: "{t[:60]}"')
    else:
        i(f'h1: "{h1s[0][:60]}"')

    if not h2s and not includes_present:
        w('No <h2> tags found — use h2s to structure content for scanners and crawlers')
    elif h2s:
        i(f'{len(h2s)} h2 tag(s) found')

    # Check for skipped heading levels
    levels = [l for l, _ in parser.headings]
    for idx in range(1, len(levels)):
        if levels[idx] > levels[idx - 1] + 1:
            w(f'Heading level skipped: h{levels[idx-1]} → h{levels[idx]} '
              f'(around: "{parser.headings[idx][1][:40]}")')

    # ── <main> landmark ───────────────────────────────────────────────────────
    if not parser.has_main:
        if includes_present:
            w('No <main> landmark in this file — may be in an included file; verify in browser')
        else:
            w('Missing <main> landmark — add <main> around primary page content '
              '(accessibility + SEO)')

    # ── Images ────────────────────────────────────────────────────────────────
    no_alt    = [img for img in parser.images if img['alt'] is None]
    empty_alt = [img for img in parser.images if img['alt'] == '']
    good_alt  = [img for img in parser.images if img['alt']]

    if no_alt:
        e(f'{len(no_alt)} image(s) missing alt attribute entirely:')
        for img in no_alt[:5]:
            e(f'  <img src="{img["src"][:60]}">')
        if len(no_alt) > 5:
            e(f'  … and {len(no_alt) - 5} more')
    if empty_alt:
        w(f'{len(empty_alt)} image(s) with empty alt="" — '
          'ok only for purely decorative images, verify intentional')
    if good_alt:
        i(f'{len(good_alt)} image(s) have descriptive alt text')

    # ── Form inputs ───────────────────────────────────────────────────────────
    unlabelled = []
    for inp in parser.inputs:
        has_label    = inp['id'] in parser.label_fors
        has_aria     = bool(inp['aria_label'])
        if not has_label and not has_aria:
            unlabelled.append(inp)

    if unlabelled:
        w(f'{len(unlabelled)} form input(s) with no <label> or aria-label '
          '(accessibility + SEO):')
        for inp in unlabelled:
            ident = inp['id'] or inp['name'] or '(no id/name)'
            w(f'  <input type="{inp["type"]}" name="{ident}">')

    # ── Includes info ────────────────────────────────────────────────────────
    if parser.includes:
        unique = list(dict.fromkeys(f'{k}:{v}' for k, v in parser.includes))
        i(f'{len(unique)} server-side include(s) detected — some content may live in included files:')
        for inc in parser.includes[:8]:
            i(f'  {inc[0]}: {inc[1]}')

    return issues


# ── Reporting ─────────────────────────────────────────────────────────────────

def report(label, issues, show_info=True):
    errs  = [(s, m) for s, m in issues if s == 'ERR']
    warns = [(s, m) for s, m in issues if s == 'WARN']
    infos = [(s, m) for s, m in issues if s == 'INFO']

    status = col('✓ PASS', GREEN) if not errs else col('✗ FAIL', RED)
    print(f'\n{BOLD}  {label}{RESET}  {status}')
    print(DIVIDER)

    for sev, msg in issues:
        if sev == 'ERR':
            prefix = col('  ERR ', RED)
        elif sev == 'WARN':
            prefix = col(' WARN ', YELLOW)
        else:
            if not show_info:
                continue
            prefix = col(' INFO ', CYAN)
        # Indent continuation lines
        lines = msg.split('\n')
        print(f'{prefix}  {lines[0]}')
        for line in lines[1:]:
            print(f'        {line}')

    print(DIVIDER)
    summary_parts = []
    if errs:
        summary_parts.append(col(f'{len(errs)} error(s)', RED))
    if warns:
        summary_parts.append(col(f'{len(warns)} warning(s)', YELLOW))
    if infos:
        summary_parts.append(col(f'{len(infos)} info', CYAN))
    print(f'  {" · ".join(summary_parts) if summary_parts else col("No issues", GREEN)}')


# ── Entry point ───────────────────────────────────────────────────────────────

def collect_files(args):
    """Expand args into list of (label, html_text) tuples."""
    sources = []

    for arg in args:
        if arg.startswith('http://') or arg.startswith('https://'):
            try:
                req = urllib.request.Request(
                    arg,
                    headers={'User-Agent': 'Mozilla/5.0 Chrome/120.0'}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    sources.append((arg, resp.read().decode('utf-8', errors='replace')))
            except urllib.error.URLError as ex:
                print(f'  Error fetching {arg}: {ex}')
        elif os.path.isdir(arg):
            for path in sorted(Path(arg).rglob('*')):
                if path.suffix.lower() in ('.html', '.shtml', '.htm'):
                    sources.append((str(path), path.read_text(errors='replace')))
        elif os.path.isfile(arg):
            sources.append((arg, Path(arg).read_text(errors='replace')))
        else:
            print(f'  Not found: {arg}')

    return sources


def main():
    args = sys.argv[1:]

    # Strip --no-info flag
    show_info = True
    if '--no-info' in args:
        show_info = False
        args = [a for a in args if a != '--no-info']

    if not args:
        print(__doc__)
        sys.exit(0)

    # Handle --live shorthand (just pass URLs through)
    args = [a for a in args if a != '--live']

    sources = collect_files(args)
    if not sources:
        print('\n  No HTML files found.\n')
        sys.exit(1)

    now = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f'\n{BOLD}  SEO Audit — {now}{RESET}')
    print(f'  {len(sources)} file(s) to audit')

    any_errors = False
    for label, html_text in sources:
        issues = audit(label, html_text)
        report(label, issues, show_info=show_info)
        if any(s == 'ERR' for s, _ in issues):
            any_errors = True

    print()
    sys.exit(1 if any_errors else 0)


if __name__ == '__main__':
    main()
