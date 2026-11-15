#!/usr/bin/env python3
"""Донести новые настройки до data/site.json на VPS, не затирая правки Натальи из админки.

update.sh обновляет только код, а data/*.json остаются серверными. Когда в коде появляется новое поле
(например addons, tagline), его надо дописать в серверный site.json — иначе сайт его не увидит.
  python3 deploy/migrate_data.py <site.json из новой версии>
Что делает: копия в data/backups/, недостающие поля верхнего уровня — из новой версии, переименования ниже.
Что уже есть на сервере (объявления, контакты, гостиница) — не меняет.
"""
import datetime, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'data', 'site.json')
RENAMES = {  # поле: (старое значение, которое заменяем) — новое берётся из новой версии
    'full_name': ('Мясная лавка БРО',),  # 14.11.2026: «ПП БРО»
}

new = json.load(open(sys.argv[1], encoding='utf-8'))
cur = json.load(open(SITE, encoding='utf-8'))
changed = []
for k, v in new.items():
    if k not in cur:
        cur[k] = v; changed.append(f'+ {k}')
for k, olds in RENAMES.items():
    if cur.get(k) in olds and new.get(k) not in (None, cur.get(k)):
        cur[k] = new[k]; changed.append(f'~ {k}')
if changed:
    bak = os.path.join(ROOT, 'data', 'backups'); os.makedirs(bak, exist_ok=True)
    shutil.copy2(SITE, os.path.join(bak, f'site-{datetime.datetime.now():%Y%m%d-%H%M%S}-before-update.json'))
    with open(SITE + '.tmp', 'w', encoding='utf-8') as f: json.dump(cur, f, ensure_ascii=False, indent=2); f.write('\n')
    os.replace(SITE + '.tmp', SITE)
print('site.json: ' + (', '.join(changed) if changed else 'без изменений'))
