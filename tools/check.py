#!/usr/bin/env python3
"""Проверка dist/ перед публикацией: битые внутренние ссылки и картинки, пустые title/description.
    python3 build.py && python3 tools/check.py
"""
import os, re, sys
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote

DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dist')

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.refs = []; self.title = ''; self.desc = None; self._t = False
    def handle_starttag(self, tag, a):
        a = dict(a)
        for k in ('href', 'src'):
            if a.get(k): self.refs.append(a[k])
        if a.get('srcset'):
            self.refs += [x.strip().split(' ')[0] for x in a['srcset'].split(',')]
        if tag == 'title': self._t = True
        if tag == 'meta' and a.get('name') == 'description': self.desc = a.get('content', '')
    def handle_endtag(self, tag):
        if tag == 'title': self._t = False
    def handle_data(self, d):
        if self._t: self.title += d

bad, pages = [], 0
for dp, _, fs in os.walk(DIST):
    for f in fs:
        if not f.endswith('.html'): continue
        path = os.path.join(dp, f); pages += 1
        p = P(); p.feed(open(path, encoding='utf-8').read())
        rel = os.path.relpath(path, DIST)
        stub = 'Страница переехала' in p.title
        if not stub and (not p.title.strip() or not p.desc):
            bad.append(f'{rel}: нет title или description')
        for ref in p.refs:
            u = urlsplit(ref)
            if u.scheme or ref.startswith(('#', 'mailto:', 'tel:', '//')): continue
            target = os.path.normpath(os.path.join(DIST, u.path.lstrip('/')) if u.path.startswith('/') else os.path.join(dp, unquote(u.path)))
            if os.path.isdir(target): target = os.path.join(target, 'index.html')
            if not os.path.exists(target):
                bad.append(f'{rel}: нет файла {ref}')
print(f'Проверено страниц: {pages}')
if bad:
    print('\n'.join(sorted(set(bad))[:60])); print(f'Проблем: {len(set(bad))}'); sys.exit(1)
print('Битых ссылок нет')
