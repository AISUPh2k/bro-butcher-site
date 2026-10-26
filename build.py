#!/usr/bin/env python3
"""Сборка сайта БРО: data/*.json + static/ -> dist/.

Запуск:  python3 build.py        (только стандартная библиотека Python 3.8+)
Результат открывается прямо из папки dist/ и заливается на любой статический хостинг.
"""
import json, os, shutil, html, datetime, urllib.parse
from urllib.parse import quote

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist')
SITE = json.load(open(os.path.join(ROOT, 'data/site.json'), encoding='utf-8'))
ALL_PRODUCTS = json.load(open(os.path.join(ROOT, 'data/products.json'), encoding='utf-8'))
PRODUCTS = [p for p in ALL_PRODUCTS if not p.get('hidden')]  # hidden — снят с сайта в админке
BY_SLUG = {p['slug']: p for p in PRODUCTS}
D = SITE['delivery']
YEAR = datetime.date.today().year
PREVIEW = os.environ.get('BRO_PREVIEW') == '1'  # показ на github.io: не индексировать, без Метрики
ORDER_API = os.environ.get('BRO_ORDER_API', '')  # адрес приёма заказов; пусто — заказ уходит в WhatsApp

CATS = [  # key, название, короткое описание
    ('mix', 'Миксы', 'Готовые рецептуры зоодиетолога'),
    ('premium', 'Премиум', 'Миксы из отборного мяса'),
    ('beef', 'Говядина', 'Мясо, обрезь, хрящи'),
    ('lamb', 'Баранина', 'Мясо и субпродукты'),
    ('poultry', 'Птица', 'Курица, утка, индейка, перепела'),
    ('rabbit', 'Кролик', 'Гипоаллергенное мясо'),
    ('offal', 'Субпродукты', 'Сердце, печень, рубец'),
    ('farsh', 'Фарш', 'Рубленое мясо'),
    ('treats', 'Лакомства', 'Сушёные, для дрессировки'),
    ('econom', 'Эконом', 'Выгодные позиции'),
    ('cats', 'Для кошек', 'Мясо и миксы для кошек'),
]
CAT_NAME = {k: n for k, n, _ in CATS}

e = html.escape

def rub(n):
    return f'{n:,}'.replace(',', ' ') + ' ₽'

def wa_link(text=''):
    return f"https://wa.me/{SITE['whatsapp']}" + (f'?text={quote(text)}' if text else '')

def sort_key(p):
    return (not p['in_stock'], p['popular'] or 999, not p['img'])

def in_cat(p, c):
    return c in p['tags']

# ---------------------------------------------------------------- icons
ICONS = {
    'cart': '<path d="M3 4h2.2l2.3 11.2h10.8l2-8H6.8"/><circle cx="9.4" cy="19.2" r="1.3"/><circle cx="16.4" cy="19.2" r="1.3"/>',
    'search': '<circle cx="10.5" cy="10.5" r="6.5"/><line x1="15.5" y1="15.5" x2="20.5" y2="20.5"/>',
    'snow': '<line x1="12" y1="3" x2="12" y2="21"/><line x1="5" y1="7" x2="19" y2="17"/><line x1="19" y1="7" x2="5" y2="17"/>',
    'leaf': '<path d="M5 19c0-8 5-13 14-14-1 9-6 14-14 14z"/><path d="M5 19l8-8"/>',
    'truck': '<rect x="2" y="9" width="11" height="7.5"/><path d="M13 11.5h4l3.2 3v2h-7.2z"/><circle cx="7" cy="18.3" r="1.6"/><circle cx="16.8" cy="18.3" r="1.6"/>',
    'wallet': '<rect x="3" y="6" width="17" height="12.5" rx="2"/><path d="M15.5 11.3h4v3.9h-4a1.95 1.95 0 010-3.9z"/>',
    'phone': '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z"/>',
    'chat': '<path d="M4 18.5l1.3-3.8A8 8 0 1112 20a8 8 0 01-3.9-1z"/>',
    'arrow': '<path d="M5 12h14M13 6l6 6-6 6"/>',
    'back': '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    'pause': '<line x1="9" y1="6" x2="9" y2="18"/><line x1="15" y1="6" x2="15" y2="18"/>',
    'play': '<path d="M8 5.5v13l10-6.5z"/>',
    'menu': '<line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/>',
    'close': '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
    'check': '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    'minus': '<line x1="6" y1="12" x2="18" y2="12"/>',
    'plus': '<line x1="6" y1="12" x2="18" y2="12"/><line x1="12" y1="6" x2="12" y2="18"/>',
    'trash': '<path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12"/>',
    'gift': '<rect x="4" y="9" width="16" height="11" rx="1"/><path d="M3 9h18M12 9v11M12 9c-2-4-6-4-6-1.5S10 9 12 9zm0 0c2-4 6-4 6-1.5S14 9 12 9z"/>',
    'home': '<path d="M4 11l8-6.5 8 6.5"/><path d="M6 9.5V20h12V9.5"/><path d="M10 20v-4.5a2 2 0 014 0V20"/>',
    'clock': '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    'pin': '<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0113 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
    'mail': '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="M3.5 7l8.5 6 8.5-6"/>',
    'vk': '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M8 8c.2 5 2.5 8 4 8s1-2.3 1-3.5c0-.9.3-1 .9-.5 1 .8 1.6 2.3 2.6 3.5.4.5 1 .6 1.7.4"/>',
    'tg': '<path d="M20.5 4.5L3.5 11l5.5 2 2 6 3-4 4.5 3.5z"/><path d="M9 13l8-5.5"/>',
}

def icon(name, cls='icon'):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')

# ---------------------------------------------------------------- layout
NAV = [('catalog.html', 'Каталог', 'catalog'), ('catalog.html?cat=mix', 'Миксы', 'mix'),
       ('catalog.html?cat=treats', 'Лакомства', 'treats'), ('delivery.html', 'Доставка и оплата', 'delivery'),
       ('catalog.html?cat=cats', 'Для кошек', 'cats'), ('hotel.html', 'Зоогостиница', 'hotel'), ('about.html', 'О нас', 'about')]

def header(r, active):
    nav = '\n'.join(f'<a href="{r}{h}"{" aria-current=\"page\"" if k == active else ""}>{t}</a>' for h, t, k in NAV)
    return f'''<a class="skip" href="#main">К содержанию</a>
<header class="site-header">
  <div class="utility-bar"><div class="wrap">
    <span>{icon("truck")}<b>Бесплатная доставка от {rub(D["free_from"])}</b> по Москве, {D["window"]}</span>
    <span class="utility-links">
      <a href="tel:{SITE["phone_raw"]}">{icon("phone")}{SITE["phone"]}</a>
      <a href="{wa_link()}" target="_blank" rel="noopener">{icon("chat")}WhatsApp</a>
    </span>
  </div></div>
  <div class="main-bar"><div class="wrap">
    <a class="logo" href="{r}index.html" aria-label="БРО — на главную">БРО<small>мясная лавка</small></a>
    <nav class="main-nav" id="mainNav" aria-label="Основное меню">
{nav}
    </nav>
    <div class="header-actions">
      <a class="icon-btn" href="{r}catalog.html#search" aria-label="Поиск по каталогу">{icon("search")}</a>
      <a class="icon-btn" href="{r}cart.html" aria-label="Корзина">{icon("cart")}<span class="cart-badge" data-cart-count hidden>0</span></a>
      <button class="icon-btn nav-toggle" id="navToggle" type="button" aria-label="Меню" aria-expanded="false" aria-controls="mainNav">{icon("menu")}</button>
    </div>
  </div></div>
</header>'''

def footer(r):
    cats = ''.join(f'<li><a href="{r}catalog.html?cat={k}">{n}</a></li>' for k, n, _ in CATS[:8])
    return f'''<footer class="site-footer">
  <div class="wrap">
    <div class="footer-grid">
      <div class="footer-brand">
        <a class="logo" href="{r}index.html">БРО<small>мясная лавка</small></a>
        <p>Натуральное мясо для собак. Пилим без разморозки, миксы составляет зоодиетолог.</p>
        <p class="slogan">{e(SITE["slogan"])}</p>
      </div>
      <div class="footer-col"><h2>Каталог</h2><ul>{cats}</ul></div>
      <div class="footer-col"><h2>Покупателям</h2><ul>
        <li><a href="{r}delivery.html">Доставка и оплата</a></li>
        <li><a href="{r}about.html">О нас</a></li>
        <li><a href="{r}hotel.html">Зоогостиница</a></li>
        <li><a href="{r}cart.html">Корзина</a></li>
      </ul></div>
      <div class="footer-col"><h2>Контакты</h2><ul class="contacts">
        <li><a href="tel:{SITE["phone_raw"]}">{icon("phone")}{SITE["phone"]}</a></li>
        <li><a href="{wa_link()}" target="_blank" rel="noopener">{icon("chat")}WhatsApp</a></li>
        <li><a href="mailto:{SITE["email"]}">{icon("mail")}{SITE["email"]}</a></li>
        <li><a href="{SITE["vk"]}" target="_blank" rel="noopener">{icon("vk")}ВКонтакте</a></li>
        <li><a href="{SITE["telegram"]}" target="_blank" rel="noopener">{icon("tg")}Telegram</a></li>
        <li><span>{icon("clock")}{SITE["hours"]}</span></li>
        <li><span>{icon("pin")}{SITE["address"]}</span></li>
      </ul></div>
    </div>
    <div class="footer-bottom">
      <span>© {SITE["founded"]}–{YEAR} {SITE["full_name"]}</span>
      <span><a href="{r}privacy.html">Политика обработки персональных данных</a> · Только доставка, самовывоза нет</span>
    </div>
  </div>
</footer>
<div class="toast" id="toast" role="status" aria-live="polite" hidden></div>
<a class="cartbar" id="cartbar" href="{r}cart.html" hidden>
  <span class="cartbar-info"><b><span data-bar-count></span> · <span data-bar-sum></span></b><small data-bar-free></small>
    <span class="cartbar-track"><span data-bar-progress></span></span></span>
  <span class="cartbar-go">Оформить {icon("arrow")}</span>
</a>'''

def metrika():
    mid = SITE.get('metrika_id')
    if not mid or PREVIEW: return ''
    return f'''<script>(function(m,e,t,r,i,k,a){{m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}})(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");ym({mid},"init",{{clickmap:true,trackLinks:true,accurateTrackBounce:true}});</script>'''

def page(path, title, desc, body, active='', og_img='static/img/brand/hero.jpg', extra_head=''):
    depth = path.count('/')
    r = '../' * depth
    full_title = title if 'БРО' in title else f'{title} — {SITE["full_name"]}'
    doc = f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
{'<meta name="robots" content="noindex, nofollow">' + chr(10) if PREVIEW else ''}<link rel="canonical" href="{SITE["base_url"]}{path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(SITE["full_name"])}">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{SITE["base_url"]}{og_img}">
<meta name="theme-color" content="#6e2430">
<link rel="icon" href="{r}static/img/brand/favicon.svg" type="image/svg+xml">
<link rel="preload" href="{r}static/fonts/Oswald-700-cyr.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{r}static/fonts/GolosText-400-cyr.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{r}static/css/style.css">
{extra_head}</head>
<body data-root="{r}">
{header(r, active)}
<main id="main">
{body}
</main>
{footer(r)}
<script src="{r}static/js/data.js"></script>
<script src="{r}static/js/app.js"></script>
{metrika()}
</body>
</html>
'''
    out = os.path.join(DIST, path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(doc)
    PAGES.append(path)

PAGES = []

# ---------------------------------------------------------------- components
CARD_SIZES = '(max-width:760px) 46vw, (max-width:1080px) 31vw, 280px'

def picture(r, img, alt, sizes=CARD_SIZES, eager=False, cls=''):
    """<picture> с WebP 400/800 и JPG-запасом; WebP готовит tools/images.py."""
    stem = img.rsplit('.', 1)[0]
    base = f'{r}static/img/products/'
    webp = ''
    if os.path.exists(os.path.join(ROOT, 'static/img/products/w400', stem + '.webp')):
        webp = f'<source type="image/webp" srcset="{base}w400/{stem}.webp 400w, {base}w800/{stem}.webp 800w" sizes="{sizes}">'
    load = ' fetchpriority="high"' if eager else ' loading="lazy"'
    c = f' class="{cls}"' if cls else ''
    return f'<picture>{webp}<img{c} src="{base}{img}" alt="{e(alt)}" width="800" height="600"{load} decoding="async"></picture>'

def photo(p, r, cls='pcard-photo', eager=False):
    if p['img']:
        return picture(r, p['img'], p['name'], '(max-width:820px) 100vw, 600px' if eager else CARD_SIZES, eager)
    return f'<span class="ph" aria-hidden="true"><span>{CAT_NAME.get(p["cat"], "БРО")}</span></span>'

HIT_MAX = 10  # popular 1..10 — «Хит» (галочка в админке)

def badges(p):
    b = []
    if not p['in_stock']: b.append('<span class="badge is-out">Нет в наличии</span>')
    if 'premium' in p['tags']: b.append('<span class="badge is-premium">Премиум</span>')
    if p['veg']: b.append('<span class="badge is-veg">С овощами</span>')
    if p['popular'] and p['popular'] <= HIT_MAX and p['in_stock']: b.append('<span class="badge">Хит</span>')
    return f'<div class="badges">{"".join(b)}</div>' if b else ''

def kbju(p, cls='kbju'):
    k = p.get('kbju')
    if not k: return ''
    cells = ''.join(f'<div><dt>{t}</dt><dd>{k.get(key, "—")}</dd></div>' for t, key in (('Б', 'b'), ('Ж', 'z'), ('У', 'u'), ('ккал', 'kcal')))
    return f'<dl class="{cls}" aria-label="Пищевая ценность на 100 г">{cells}</dl>'

def options(p):
    opts = p['options']
    if len(opts) == 1:
        return ''
    btns = ''.join(
        f'<button type="button" class="opt" data-opt="{e(l)}" data-price="{pr}" aria-pressed="{"true" if i == len(opts) - 1 else "false"}">{e(l)}</button>'
        for i, (l, pr) in enumerate(opts))
    return f'<div class="opts" role="group" aria-label="Фасовка">{btns}</div>'

def buy_button(p, big=False):
    cls = 'btn btn-primary btn-block' if big else 'add-btn'
    if 'opt' in p['tags']:
        txt = f'Здравствуйте! Интересует опт: {p["name"]}, от 100 кг.'
        return f'<a class="{cls} is-wa" href="{wa_link(txt)}" target="_blank" rel="noopener">Запросить опт</a>'
    if not p['in_stock']:
        return f'<button class="{cls}" type="button" disabled>Нет в наличии</button>'
    label, _ = p['options'][-1]
    return f'<button class="{cls}" type="button" data-add="{p["slug"]}" data-opt="{e(label)}">В корзину</button>'

def card(p, r):
    label, price = p['options'][-1]
    unit = 'за кг, от 100 кг' if 'opt' in p['tags'] else f'за {label}'
    comp = ''
    if p['composition']:
        short = ', '.join(c.split(' — ')[0].lower() for c in p['composition'][:4])
        comp = f'<p class="pcard-comp">{e(short[:1].upper() + short[1:])}{"…" if len(p["composition"]) > 4 else ""}</p>'
    return f'''<article class="pcard{" is-out" if not p["in_stock"] else ""}" data-slug="{p["slug"]}" data-tags="{" ".join(p["tags"])}" data-price="{price}" data-pop="{p["popular"] or 999}" data-stock="{1 if p["in_stock"] else 0}" data-name="{e(p["name"].lower())}">
  <a class="pcard-photo" href="{r}p/{p["slug"]}.html" tabindex="-1" aria-hidden="true">{photo(p, r)}</a>
  {badges(p)}
  <h3><a href="{r}p/{p["slug"]}.html">{e(p["name"])}</a></h3>
  {comp}{kbju(p)}
  <div class="pcard-bottom">
    {options(p)}
    <div class="price-row"><span class="price" data-price-out>{rub(price)}</span><span class="unit" data-unit-out>{unit}</span></div>
    {buy_button(p)}
  </div>
</article>'''

def grid(items, r, cls='pgrid'):
    return f'<div class="{cls}">' + '\n'.join(card(p, r) for p in items) + '</div>'

def wa_btn(text, label, cls='btn btn-primary'):
    return f'<a class="{cls}" href="{wa_link(text)}" target="_blank" rel="noopener">{icon("chat")}{label}</a>'

# ---------------------------------------------------------------- pages
# ---------------------------------------------------------------- слайдер на главной
TODAY = datetime.date.today().isoformat()
SLIDES = [sl for sl in SITE.get('slides', []) if not sl.get('off') and (not sl.get('until') or sl['until'] >= TODAY)]

# иллюстрация для слайда гостиницы, пока нет фото: домик с сердцем и следы лап к двери
PAW = '<g><ellipse cx="0" cy="6" rx="9" ry="7.5"/><ellipse cx="-9" cy="-6" rx="3.6" ry="4.6"/><ellipse cx="-3.2" cy="-11" rx="3.6" ry="4.6"/><ellipse cx="3.2" cy="-11" rx="3.6" ry="4.6"/><ellipse cx="9" cy="-6" rx="3.6" ry="4.6"/></g>'
HOTEL_SVG = ('<svg class="arch-ill" viewBox="0 0 400 500" aria-hidden="true">'
    '<path class="arch-bg" d="M0 500V200a200 200 0 0 1 400 0v300z"/>'
    '<g class="arch-house" fill="none" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M96 246 200 158l104 88"/><path d="M122 226v132h156V226"/><path d="M178 358v-50a22 22 0 0 1 44 0v50"/></g>'
    '<path class="arch-heart" d="M200 236c-12-14-34-10-34 7 0 14 19 24 34 36 15-12 34-22 34-36 0-17-22-21-34-7z"/>'
    '<g class="arch-paws">'
    + ''.join(f'<g transform="translate({x} {y}) rotate({r}) scale({k})">{PAW}</g>' for x, y, r, k in
              ((70, 478, -32, 1.25), (118, 452, -26, 1.2), (140, 412, -18, 1.1), (186, 396, -6, 1.05)))
    + '</g></svg>')

def hotel_art(sl):
    feats = [f for f in SITE['hotel'].get('features', []) if '24/7' not in f[1]][:3]
    notes = ''.join(f'<li style="--i:{n}">{icon(ic)}<span>{e(t)}</span></li>' for n, (ic, t) in enumerate(feats))
    inner = (picture('', sl['img'], 'Зоогостиница БРО', '(max-width:860px) 80vw, 420px', cls='arch-photo') if sl.get('img') else HOTEL_SVG)
    return f'''<div class="slide-art hotel-arch">
      <div class="arch">{inner}</div>
      <span class="arch-stamp" aria-hidden="true">Рядом<br><b>24/7</b></span>
      <ul class="arch-notes">{notes}</ul>
    </div>'''

def slides_html():
    out = ''
    for i, sl in enumerate(SLIDES, 2):
        dark = sl.get('theme') in ('olive', 'burgundy')
        if sl['link'] == 'whatsapp':
            href, ext = wa_link(sl.get('wa_text', '')), ' target="_blank" rel="noopener"'
        else:
            href = sl['link']
            ext = ' target="_blank" rel="noopener"' if href.startswith('http') else ''
        if sl.get('art') == 'hotel':
            art = hotel_art(sl)
        elif sl.get('img'):
            art = f'<div class="slide-art has-img">{picture("", sl["img"], "", "(max-width:860px) 92vw, 560px")}</div>'
        else:
            art = f'<div class="slide-art" aria-hidden="true">{icon(sl.get("icon", "gift"))}</div>'
        until = f' data-until="{e(sl["until"])}"' if sl.get('until') else ''
        out += f'''<div class="slide hero slide-{e(sl.get("theme", "light"))}" role="group" aria-roledescription="slide" aria-label="{i} из {len(SLIDES) + 1}"{until}>
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="eyebrow{" eyebrow-light" if dark else ""}">{e(sl["eyebrow"])}</p>
      <h2 class="slide-title">{e(sl["title"])}</h2>
      <p class="hero-lede">{e(sl["text"])}</p>
      <div class="hero-actions"><a class="btn {"btn-brass" if dark else "btn-primary"}" href="{e(href)}"{ext}>{e(sl["button"])} {icon("arrow")}</a></div>
    </div>
    {art}
  </div>
</div>
'''
    return out

def slider_controls():
    if not SLIDES: return ''
    dots = ''.join(f'<button class="dot" type="button" data-go="{i}" aria-label="Слайд {i + 1}"><span></span></button>'
                   for i in range(len(SLIDES) + 1))
    return f'''<div class="slider-ui wrap" hidden>
  <div class="slider-bar">
    <div class="dots">{dots}</div>
    <button class="slider-btn" type="button" data-prev aria-label="Предыдущий слайд">{icon("back")}</button>
    <button class="slider-btn" type="button" data-next aria-label="Следующий слайд">{icon("arrow")}</button>
    <button class="slider-btn" type="button" data-pause aria-label="Остановить прокрутку">{icon("pause", "icon i-pause")}{icon("play", "icon i-play")}</button>
  </div>
</div>'''

def build_home():
    r = ''
    tiles = ''
    for k, n, sub in [c for c in CATS if c[0] in ('mix', 'premium', 'beef', 'lamb', 'poultry', 'offal', 'treats', 'cats')]:
        items = sorted([p for p in PRODUCTS if in_cat(p, k)], key=sort_key)
        pic = next((p for p in items if p['img']), None)
        img = picture('', pic['img'], '', '(max-width:900px) 48vw, 290px') if pic else f'<span class="tile-ph" aria-hidden="true">{icon("leaf")}</span>'
        count = len(items) if items else 'скоро'
        tiles += f'<a class="tile" href="catalog.html?cat={k}">{img}<span class="tile-text"><b>{n}</b><small>{sub} · {count}</small></span></a>\n'
    hits = sorted([p for p in PRODUCTS if p['in_stock'] and 'opt' not in p['tags'] and p['img']], key=sort_key)[:8]
    first = f'Здравствуйте! Хочу перевести собаку на натуральное питание, нужна консультация.'
    body = f'''<section class="hero-slider" id="heroSlider" aria-roledescription="carousel" aria-label="Главное и объявления">
<div class="slides" id="heroSlides">
<div class="slide hero" role="group" aria-roledescription="slide" aria-label="1 из {len(SLIDES) + 1}">
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="eyebrow">Мясная лавка БРО · своё производство</p>
      <h1>Честное мясо для&nbsp;вашей собаки</h1>
      <p class="hero-lede">Говядина, баранина, птица и готовые миксы для натурального кормления. Мясо приходит с бойни замороженным, и мы пилим его на порции, не размораживая. Рецептуры миксов составляет зоодиетолог.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="catalog.html">Выбрать мясо {icon("arrow")}</a>
        <a class="btn-ghost" href="#craft">Как мы работаем ↓</a>
      </div>
      <p class="hero-meta">Доставка по Москве и области · оплата после получения</p>
    </div>
    <div class="hero-visual">
      <picture><source type="image/webp" srcset="static/img/brand/w600/hero.webp 600w, static/img/brand/w1100/hero.webp 1100w" sizes="(max-width:860px) 92vw, 560px"><img class="hero-photo" src="static/img/brand/hero.jpg" alt="Микс «Вайс Премиум»: кубики говядины и сердца на деревянной доске" width="1100" height="880" fetchpriority="high"></picture>
      <div class="stamp-badge" aria-hidden="true">БЕЗ<br>РАЗМОРОЗКИ<br>НИ РАЗУ</div>
      <a class="hero-note" href="{wa_link(first)}" target="_blank" rel="noopener"><b>Первая консультация бесплатно</b><span>Поможем перейти на натуральное питание {icon("arrow")}</span></a>
    </div>
  </div>
</div>
{slides_html()}</div>
{slider_controls()}
</section>

<section class="trust" aria-label="Наши преимущества">
  <div class="wrap trust-grid">
    <div class="trust-item">{icon("snow")}<p><b>Ни разу не разморожено</b>пилим прямо из замороженного блока, мясо не теряет сок</p></div>
    <div class="trust-item">{icon("leaf")}<p><b>Рецептуры зоодиетолога</b>каждый микс составлен специалистом по питанию собак</p></div>
    <div class="trust-item">{icon("truck")}<p><b>Бесплатно от {rub(D["free_from"])}</b>доставка в пределах МКАД, вечером {D["window"]}</p></div>
    <div class="trust-item">{icon("wallet")}<p><b>Оплата после получения</b>наличными курьеру, без предоплаты</p></div>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="section-head"><h2>Что выбрать</h2><a class="link-more" href="catalog.html">Весь каталог · {len(PRODUCTS)} позиций {icon("arrow")}</a></div>
    <div class="tiles">
{tiles}    </div>
  </div>
</section>

<section class="section section-alt">
  <div class="wrap">
    <div class="section-head"><h2>Покупают чаще всего</h2><a class="link-more" href="catalog.html">Смотреть все {icon("arrow")}</a></div>
    {grid(hits, r)}
  </div>
</section>

{craft_section(r)}

<section class="consult">
  <div class="wrap consult-grid">
    <div>
      <p class="eyebrow eyebrow-light">Бесплатно</p>
      <h2>Первая консультация по&nbsp;переходу на&nbsp;натуральное питание</h2>
      <p>Расскажите о собаке: возраст, вес, порода, особенности здоровья. Зоодиетолог подберёт рацион, миксы и расфасовку.</p>
    </div>
    {wa_btn(first, "Написать зоодиетологу", "btn btn-brass")}
  </div>
</section>

{steps_section(r)}'''
    page('index.html', 'Мясо для собак с доставкой по Москве — мясная лавка БРО',
         'Натуральное мясо и миксы для собак: говядина, баранина, птица, лакомства. Пилим без разморозки, рецептуры зоодиетолога. Бесплатная доставка по Москве от 5000 ₽.',
         body, 'home')

CRAFT_PHOTO = 'obrez-govyazhya-v-kubikah.jpg'  # кубики в инее — видно, что мясо не размораживали

def craft_section(r):
    ex = SITE['expert']
    steps = [('Блоки по 20 кг', 'Берём мясо с бойни уже замороженным, большими партиями.'),
             ('Пилим без разморозки', 'Режем на кубики прямо из блока — мясо не оттаивает ни на минуту.'),
             ('Рецептуры зоодиетолога', f'Каждый микс составляет {ex["name"]}, зоодиетолог.')]
    lis = ''.join(f'<li><span class="craft-n">{i:02d}</span><h3>{t}</h3><p>{d}</p></li>' for i, (t, d) in enumerate(steps, 1))
    photo = picture(r, CRAFT_PHOTO, 'Замороженные кубики говяжьей обрези в пакете', '(max-width:860px) 92vw, 520px', cls='craft-photo') \
        if os.path.exists(os.path.join(ROOT, 'static/img/products', CRAFT_PHOTO)) else ''
    return f'''<section class="craft" id="craft">
  <div class="wrap craft-grid">
    <div>
      <p class="eyebrow">Как мы делаем</p>
      <h2>Мясо ни&nbsp;разу не&nbsp;размораживается</h2>
      <p class="craft-lede">Обычно сырьё размораживают и замораживают заново, теряя сок. У нас мясо остаётся замороженным от бойни до вашей морозилки.</p>
      <ol class="craft-steps">{lis}</ol>
    </div>
    <figure class="craft-figure">{photo}<figcaption>Так выглядит обрезь после распила: в инее, без следов оттаивания</figcaption></figure>
  </div>
</section>'''

def steps_section(r):
    return f'''<section class="section steps-section">
  <div class="wrap">
    <h2 class="center">Как доходит до вас</h2>
    <ol class="steps-row">
      <li><span class="n">01</span><p>Собираете корзину на сайте и отправляете заказ в WhatsApp, или просто пишете нам</p></li>
      <li><span class="n">02</span><p>Подтверждаем заказ и собираем его прямо из морозильной камеры</p></li>
      <li><span class="n">03</span><p>Привозим вечером, {D["window"]}, до подъезда</p></li>
      <li><span class="n">04</span><p>Оплачиваете наличными курьеру после получения</p></li>
    </ol>
    <p class="center"><a class="link-more" href="{r}delivery.html">Все условия доставки {icon("arrow")}</a></p>
  </div>
</section>'''

def build_catalog():
    r = ''
    items = sorted(PRODUCTS, key=sort_key)
    chips = '<button type="button" class="chip is-active" data-filter="all" aria-pressed="true">Все <small>' + str(len(PRODUCTS)) + '</small></button>'
    for k, n, _ in CATS:
        cnt = sum(1 for p in PRODUCTS if in_cat(p, k))
        if cnt or k == 'cats':  # «Для кошек» показываем и пустым — раздел наполняется через админку
            chips += f'<button type="button" class="chip" data-filter="{k}" aria-pressed="false">{n} <small>{cnt or "скоро"}</small></button>'
    body = f'''<section class="page-head">
  <div class="wrap">
    <nav class="crumbs" aria-label="Навигация"><a href="index.html">Главная</a><span>Каталог</span></nav>
    <h1>Каталог</h1>
    <p class="lede">Всё мясо — сырое, свежемороженое, распилено без разморозки. Цена указана за выбранную фасовку.</p>
  </div>
</section>
<section class="catalog-section">
  <div class="wrap">
    <div class="chips" id="chips" role="group" aria-label="Категории">{chips}</div>
    <div class="toolbar">
      <label class="search">{icon("search")}<input id="search" type="search" placeholder="Найти: рубец, утка, премиум…" autocomplete="off" aria-label="Поиск по каталогу"></label>
      <label class="select"><span>Сортировка</span><select id="sort">
        <option value="pop">Сначала популярные</option><option value="asc">Сначала дешевле</option>
        <option value="desc">Сначала дороже</option><option value="name">По названию</option></select></label>
      <label class="check"><input type="checkbox" id="inStock" checked> Только в наличии</label>
      <span class="found" id="found" aria-live="polite"></span>
    </div>
    <div class="pgrid" id="catalogGrid">
{"".join(card(p, r) for p in items)}
    </div>
    <div class="empty" id="catsSoon" hidden><p>Раздел для кошек скоро появится. Пока можно <a href="{wa_link("Здравствуйте! Интересует питание для кошки: ")}" target="_blank" rel="noopener">спросить нас в WhatsApp</a> — подберём.</p></div>
    <div class="empty" id="catalogEmpty" hidden><p>Ничего не нашлось. Попробуйте другой запрос или <a href="{wa_link("Здравствуйте! Ищу для собаки: ")}" target="_blank" rel="noopener">спросите нас в WhatsApp</a>: подберём замену.</p></div>
  </div>
</section>'''
    page('catalog.html', 'Каталог мяса для собак', 'Каталог мяса для собак: миксы зоодиетолога, говядина, баранина, птица, субпродукты, сушёные лакомства, питание для кошек.', body, 'catalog')

def build_product(p):
    r = '../'
    label, price = p['options'][-1]
    unit = 'за кг, от 100 кг' if 'opt' in p['tags'] else f'за {label}'
    comp = ''
    if p['composition']:
        lis = ''.join(f'<li>{e(c)}</li>' for c in p['composition'])
        comp = f'<div class="info-block"><h2>Состав</h2><ul class="comp-list">{lis}</ul></div>'
    notes = ''.join(f'<p>{e(n)}</p>' for n in p['notes'])
    if notes: notes = f'<div class="info-block prose">{notes}</div>'
    kb = f'<div class="info-block"><h2>Пищевая ценность на 100 г</h2>{kbju(p, "kbju kbju-lg")}</div>' if p.get('kbju') else ''
    cat = p['cat']
    similar = sorted([q for q in PRODUCTS if q['slug'] != p['slug'] and in_cat(q, cat) and q['in_stock']], key=sort_key)[:4]
    qty = '' if ('opt' in p['tags'] or not p['in_stock']) else f'''<div class="qty" data-qty>
        <button type="button" data-qty-dec aria-label="Меньше">{icon("minus")}</button><input type="number" min="1" max="99" value="1" aria-label="Количество" data-qty-input><button type="button" data-qty-inc aria-label="Больше">{icon("plus")}</button></div>'''
    ask = f'Здравствуйте! Вопрос по товару «{p["name"]}».'
    stock = '<span class="stock is-in">В наличии</span>' if p['in_stock'] else '<span class="stock is-out">Нет в наличии — уточните сроки поступления</span>'
    body = f'''<section class="product-page">
  <div class="wrap">
    <nav class="crumbs" aria-label="Навигация"><a href="{r}index.html">Главная</a><a href="{r}catalog.html">Каталог</a><a href="{r}catalog.html?cat={cat}">{CAT_NAME[cat]}</a><span>{e(p["name"])}</span></nav>
    <div class="product-grid pcard" data-slug="{p["slug"]}">
      <div class="product-photo">{photo(p, r, eager=True)}</div>
      <div class="product-info">
        {badges(p)}
        <h1>{e(p["name"])}</h1>
        {stock}
        {options(p)}
        <div class="price-row big"><span class="price" data-price-out>{rub(price)}</span><span class="unit" data-unit-out>{unit}</span></div>
        <div class="buy-row">{qty}{buy_button(p, big=True)}</div>
        <a class="ask" href="{wa_link(ask)}" target="_blank" rel="noopener">{icon("chat")}Задать вопрос зоодиетологу</a>
        <ul class="facts">
          <li>{icon("snow")}Сырое, свежемороженое, распилено без разморозки</li>
          <li>{icon("truck")}Доставка {D["window"]}, бесплатно от {rub(D["free_from"])} в пределах МКАД</li>
          <li>{icon("wallet")}Оплата наличными после получения</li>
        </ul>
      </div>
    </div>
    <div class="product-details">{comp}{kb}{notes}</div>
  </div>
</section>
{f'<section class="section section-alt"><div class="wrap"><div class="section-head"><h2>Похожие позиции</h2><a class="link-more" href="{r}catalog.html?cat={cat}">Все: {CAT_NAME[cat].lower()} {icon("arrow")}</a></div>{grid(similar, r)}</div></section>' if similar else ''}'''
    desc_bits = ', '.join(c.split(' — ')[0].lower() for c in p['composition'][:5])
    desc = f'{p["name"]} для собак — {rub(price)} {unit}.' + (f' Состав: {desc_bits}.' if desc_bits else '') + ' Свежемороженое, без разморозки. Доставка по Москве.'
    og = f'static/img/products/{p["img"]}' if p['img'] else 'static/img/brand/hero.jpg'
    ld = {'@context': 'https://schema.org', '@type': 'Product', 'name': p['name'], 'description': desc,
          'offers': {'@type': 'Offer', 'priceCurrency': 'RUB', 'price': price,
                     'availability': 'https://schema.org/' + ('InStock' if p['in_stock'] else 'OutOfStock')}}
    if p['img']: ld['image'] = SITE['base_url'] + og
    head = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n'
    page(f'p/{p["slug"]}.html', p['name'], desc, body, 'catalog', og, head)

def build_cart():
    body = f'''<section class="page-head">
  <div class="wrap">
    <nav class="crumbs" aria-label="Навигация"><a href="index.html">Главная</a><span>Корзина</span></nav>
    <h1>Корзина</h1>
  </div>
</section>
<section class="cart-section">
  <div class="wrap">
    <div id="cartEmpty" class="empty" hidden>
      <p>Корзина пока пуста.</p>
      <a class="btn btn-primary" href="catalog.html">Перейти в каталог {icon("arrow")}</a>
    </div>
    <div class="cart-grid" id="cartApp" hidden>
      <div>
        <ul class="cart-list" id="cartList"></ul>
        <button type="button" class="btn-ghost" id="cartClear">Очистить корзину</button>
      </div>
      <form class="checkout" id="checkout" novalidate>
        <h2>Оформление</h2>
        <div class="field"><label for="f-name">Имя</label><input id="f-name" name="name" autocomplete="name" required></div>
        <div class="field"><label for="f-phone">Телефон</label><input id="f-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="+7 (900) 123-45-67" maxlength="18" required></div>
        <div class="field"><label for="f-addr">Адрес доставки</label><input id="f-addr" name="address" autocomplete="street-address" required></div>
        <fieldset class="field"><legend>Зона доставки</legend>
          <label class="radio"><input type="radio" name="zone" value="mkad" checked> Москва в пределах МКАД</label>
          <label class="radio"><input type="radio" name="zone" value="out"> За МКАД <small>+{D["outside_per_km"]}&nbsp;₽/км, точную сумму сообщим</small></label>
        </fieldset>
        <p class="pay-note">{icon("wallet")}Оплата наличными курьеру после получения заказа</p>
        <div class="field"><label for="f-comment">Комментарий <small>(необязательно)</small></label><textarea id="f-comment" name="comment" rows="3" placeholder="Подъезд, этаж, удобное время, вопросы зоодиетологу"></textarea></div>
        <dl class="totals">
          <div><dt>Товары</dt><dd id="tItems">—</dd></div>
          <div><dt>Доставка</dt><dd id="tDelivery">—</dd></div>
          <div class="total"><dt>Итого</dt><dd id="tTotal">—</dd></div>
        </dl>
        <p class="hint" id="minHint" hidden></p>
        <label class="check consent"><input type="checkbox" name="consent" id="f-consent"> <span>Даю согласие на обработку персональных данных в соответствии с <a href="privacy.html" target="_blank">политикой</a></span></label>
        <p class="hint error" id="formError" hidden></p>
        <input type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true" class="hp">
        <button class="btn btn-primary btn-block" type="submit" id="sendOrder">{icon("cart" if ORDER_API else "chat")}{"Оформить заказ" if ORDER_API else "Отправить заказ в WhatsApp"}</button>
        <p class="hint">Доставляем {D["window"]}. Доставка к определённому времени — от {rub(D["timed_fee_from"])}. {"Мы перезвоним, чтобы подтвердить заказ и итоговую сумму." if ORDER_API else "Менеджер подтвердит заказ и итоговую сумму в WhatsApp."}</p>
      </form>
    </div>
    <div class="order-done" id="orderDone" hidden tabindex="-1"></div>
  </div>
</section>'''
    page('cart.html', 'Корзина', 'Корзина заказа мясной лавки БРО.', body, 'cart')

def build_delivery():
    body = f'''<section class="page-head">
  <div class="wrap">
    <nav class="crumbs" aria-label="Навигация"><a href="index.html">Главная</a><span>Доставка и оплата</span></nav>
    <h1>Доставка и оплата</h1>
    <p class="lede">Работаем только с доставкой, самовывоза нет. Заказ можно собрать на сайте или сразу написать нам в WhatsApp.</p>
  </div>
</section>
<section class="section">
  <div class="wrap terms">
    <div class="term"><span class="term-num">{rub(D["min_order"])}</span><h2>Минимальный заказ</h2><p>Сумма товаров без учёта доставки.</p></div>
    <div class="term"><span class="term-num">0&nbsp;₽</span><h2>Доставка от {rub(D["free_from"])}</h2><p>По Москве в пределах МКАД. Для заказов меньше {rub(D["free_from"])} — {rub(D["fee"])}.</p></div>
    <div class="term"><span class="term-num">19–23</span><h2>Время доставки</h2><p>Привозим вечером, {D["window"]}, до подъезда. К определённому времени — от {rub(D["timed_fee_from"])}.</p></div>
    <div class="term"><span class="term-num">+{D["outside_per_km"]}&nbsp;₽</span><h2>За МКАД</h2><p>За каждый километр от МКАД. Точную стоимость сообщим после оформления заказа.</p></div>
  </div>
</section>
<section class="section section-alt">
  <div class="wrap two-col">
    <div class="prose">
      <h2>Оплата</h2>
      <p>Оплата производится <b>наличными курьеру после получения заказа</b>. Предоплата не нужна.</p>
    </div>
    <div class="prose">
      <h2>Как оформить заказ</h2>
      <ol><li>Соберите корзину на сайте и нажмите «Отправить заказ в WhatsApp» — текст заказа сформируется сам.</li>
      <li>Или напишите нам в WhatsApp: <a href="{wa_link()}" target="_blank" rel="noopener">{SITE["phone"]}</a>.</li>
      <li>Менеджер подтвердит наличие, сумму и время доставки.</li></ol>
      <p>Принимаем заказы: {SITE["hours"]}.</p>
    </div>
  </div>
</section>
'''
    page('delivery.html', 'Доставка и оплата', f'Доставка мяса для собак по Москве {D["window"]}: бесплатно от {D["free_from"]} ₽ в пределах МКАД, минимальный заказ {D["min_order"]} ₽. Оплата после получения.', body, 'delivery')

def build_about():
    body = f'''<section class="page-head">
  <div class="wrap">
    <nav class="crumbs" aria-label="Навигация"><a href="index.html">Главная</a><span>О нас</span></nav>
    <h1>О нас</h1>
    <p class="lede">БРО — небольшое производство натурального мяса для собак в Подмосковье. Работаем с {SITE["founded"]} года.</p>
  </div>
</section>
{craft_section('')}
<section class="section">
  <div class="wrap two-col">
    <div class="prose">
      <h2>Что мы делаем</h2>
      <p>Говядина, баранина, птица, кролик и субпродукты для натурального кормления, готовые миксы — с овощами и без, сушёные лакомства. Фасуем порциями — вес и цена указаны у каждого товара.</p>
    </div>
    <div class="prose">
      <h2>Где мы</h2>
      <p>Производство: {SITE["address"]}. Доставляем по Москве и области, самовывоза нет.</p>
      <p>Телефон и WhatsApp: <a href="tel:{SITE["phone_raw"]}">{SITE["phone"]}</a><br>Почта: <a href="mailto:{SITE["email"]}">{SITE["email"]}</a><br>{SITE["hours"]}</p>
    </div>
  </div>
</section>'''
    page('about.html', 'О нас', 'Мясная лавка БРО: своё производство в Подмосковье, мясо пилим без разморозки, миксы составляет зоодиетолог.', body, 'about')

def build_privacy():
    op = SITE.get('operator', {})
    name = op.get('name') or SITE['full_name']
    req = ', '.join(x for x in (
        f'ИНН {op["inn"]}' if op.get('inn') else '', f'ОГРН/ОГРНИП {op["ogrn"]}' if op.get('ogrn') else '',
        f'адрес: {op["address"]}' if op.get('address') else '') if x)
    mail = SITE.get('privacy_email') or SITE['email']
    url = SITE['base_url'].rstrip('/')
    sections = [
        ('1. Общие положения', [
            f'Настоящая политика составлена в соответствии с Федеральным законом от 27.07.2006 № 152-ФЗ «О персональных данных» и определяет порядок обработки персональных данных и меры по их защите, которые принимает {name}{" (" + req + ")" if req else ""} (далее — Оператор).',
            f'Политика применяется ко всей информации, которую Оператор может получить о посетителях сайта {url} (далее — Пользователи).',
        ]),
        ('2. Какие данные обрабатываются', [
            'При оформлении заказа или обращении: имя; номер телефона; адрес доставки; комментарий к заказу, если Пользователь его оставил; содержание переписки при обращении в мессенджерах.',
            'Обезличенные данные о посещении сайта (файлы cookie, IP-адрес, сведения о браузере и устройстве, действия на сайте) с помощью сервиса Яндекс Метрика.',
            'Оператор не обрабатывает специальные категории персональных данных (о расовой и национальной принадлежности, политических взглядах, религиозных убеждениях, здоровье, интимной жизни) и биометрические данные.',
        ]),
        ('3. Цели обработки', [
            'Приём, подтверждение и доставка заказов; связь с Пользователем по вопросам заказа.',
            'Консультации по питанию животных — по запросу Пользователя.',
            'Анализ посещаемости и улучшение сайта — только в обезличенном виде.',
            'Рекламные и информационные сообщения направляются только при наличии отдельного согласия Пользователя; от них можно отказаться в любой момент.',
        ]),
        ('4. Правовые основания', [
            'Согласие Пользователя на обработку персональных данных (п. 1 ч. 1 ст. 6 Закона о персональных данных).',
            'Заключение и исполнение договора купли-продажи, стороной которого является Пользователь (п. 5 ч. 1 ст. 6 Закона о персональных данных).',
        ]),
        ('5. Как обрабатываются данные', [
            'Сайт не хранит персональные данные на сервере. Содержимое корзины хранится только в браузере Пользователя. При нажатии «Отправить заказ» сайт формирует текст заказа, который Пользователь сам отправляет Оператору через мессенджер WhatsApp или передаёт по телефону.',
            'Для доставки заказа имя, телефон и адрес передаются курьеру, выполняющему доставку.',
            'Мессенджеры и сервисы статистики обрабатывают данные в соответствии со своими правилами. Оператором мессенджера WhatsApp является иностранная компания, поэтому отправка заказа через WhatsApp может сопровождаться трансграничной передачей данных. Пользователь, не желающий этого, может оформить заказ по телефону.',
            'Оператор не продаёт и не передаёт персональные данные третьим лицам, кроме случаев, указанных выше или предусмотренных законодательством РФ.',
        ]),
        ('6. Сроки обработки', [
            'Персональные данные обрабатываются до достижения целей обработки либо до отзыва согласия Пользователем, если более длительный срок не предусмотрен законом. После этого данные уничтожаются или обезличиваются.',
        ]),
        ('7. Права Пользователя', [
            'Пользователь вправе получить сведения об обработке своих данных, потребовать их уточнения, блокирования или уничтожения, отозвать согласие на обработку, а также обжаловать действия Оператора в Роскомнадзоре или в суде.',
            f'Для этого достаточно написать на {mail} или позвонить по телефону {SITE["phone"]}. Оператор отвечает на запросы в сроки, установленные Законом о персональных данных.',
        ]),
        ('8. Защита данных', [
            'Оператор принимает правовые, организационные и технические меры для защиты персональных данных от неправомерного доступа, уничтожения, изменения, блокирования, копирования и распространения.',
        ]),
        ('9. Файлы cookie', [
            'Сайт использует файлы cookie и сервис Яндекс Метрика для анализа посещаемости. Пользователь может отключить cookie в настройках браузера; основные функции сайта, включая корзину, при этом продолжат работать.',
        ]),
        ('10. Заключительные положения', [
            f'Оператор вправе вносить изменения в Политику. Актуальная версия всегда доступна по адресу {url}/privacy.html. Редакция от {SITE.get("policy_date", "")}.',
        ]),
    ]
    html_s = ''.join(f'<h2>{e(h)}</h2>' + ''.join(f'<p>{e(t)}</p>' for t in ps) for h, ps in sections)
    body = f'''<section class="page-head">
  <div class="wrap">
    <nav class="crumbs" aria-label="Навигация"><a href="index.html">Главная</a><span>Политика обработки персональных данных</span></nav>
    <h1>Политика обработки персональных данных</h1>
  </div>
</section>
<section class="section">
  <div class="wrap narrow"><div class="prose policy">{html_s}</div></div>
</section>'''
    page('privacy.html', 'Политика обработки персональных данных', 'Политика мясной лавки БРО в отношении обработки персональных данных пользователей сайта.', body)


def build_hotel():
    h = SITE['hotel']
    rows = ''
    if h.get('hours'): rows += f'<div class="term"><span class="term-num">{icon("clock")}</span><h2>Режим работы</h2><p>{e(h["hours"])}</p></div>'
    if h.get('address'): rows += f'<div class="term"><span class="term-num">{icon("pin")}</span><h2>Адрес</h2><p>{e(h["address"])}</p></div>'
    prices = ''.join(f'<li><span>{e(n)}</span><b>{e(v)}</b></li>' for n, v in h.get('prices', []))
    prices = f'<div class="info-block"><h2>Стоимость</h2><ul class="price-list">{prices}</ul></div>' if prices else ''
    text = ''.join(f'<p>{e(t)}</p>' for t in h.get('text', []))
    feats = ''.join(f'<li>{icon(ic)}<span>{e(t)}</span></li>' for ic, t in h.get('features', []))
    photo = (picture('', h['img'], 'Зоогостиница БРО', '(max-width:860px) 92vw, 520px', cls='hotel-photo')
             if h.get('img') else f'<div class="hotel-art" aria-hidden="true">{icon("home")}</div>')
    msg = 'Здравствуйте! Хочу забронировать место в зоогостинице. Питомец (вид, порода): , даты: '
    book = f'''<div class="hotel-book">
      <p><b>Забронировать место</b><span>Напишите вид и породу питомца и даты — ответим и всё расскажем.</span></p>
      <div class="hotel-book-btns">{wa_btn(msg, "Написать в WhatsApp")}<a class="btn btn-ghost-dark" href="tel:{SITE["phone_raw"]}">{icon("phone")}{SITE["phone"]}</a></div>
    </div>'''
    body = f'''<section class="page-head">
  <div class="wrap">
    <nav class="crumbs" aria-label="Навигация"><a href="index.html">Главная</a><span>Зоогостиница</span></nav>
    <p class="eyebrow">{e(h["title"])}</p>
    <h1>{e(h.get("tagline") or h["title"])}</h1>
  </div>
</section>
<section class="section hotel">
  <div class="wrap hotel-grid">
    <div class="prose hotel-text">{text}
      {f'<ul class="hotel-feats">{feats}</ul>' if feats else ''}
    </div>
    <div class="hotel-visual">{photo}</div>
  </div>
  <div class="wrap">
    {f'<div class="terms">{rows}</div>' if rows else ''}
    {f'<div class="product-details">{prices}</div>' if prices else ''}
    {book}
  </div>
</section>'''
    page('hotel.html', h['title'], f'{h["title"]}: тёплые номера, забота, игры и натуральное питание. Бронирование по телефону и в WhatsApp {SITE["phone"]}.', body, 'hotel')

def build_404():
    body = f'''<section class="page-head center"><div class="wrap narrow">
  <h1>Страница не найдена</h1>
  <p class="lede">Возможно, товар переехал. Загляните в каталог.</p>
  <p><a class="btn btn-primary" href="/catalog.html">В каталог {icon("arrow")}</a></p>
</div></section>'''
    page('404.html', 'Страница не найдена', 'Страница не найдена.', body)

# ---------------------------------------------------------------- data + assets
def write_data_js():
    data = {
        'site': dict({k: SITE[k] for k in ('phone', 'whatsapp', 'delivery')}, order_api=ORDER_API),
        'products': {p['slug']: {'n': p['name'], 'i': p['img'], 'o': p['options'], 's': int(p['in_stock'])}
                     for p in PRODUCTS if 'opt' not in p['tags']},
    }
    os.makedirs(os.path.join(DIST, 'static/js'), exist_ok=True)
    open(os.path.join(DIST, 'static/js/data.js'), 'w', encoding='utf-8').write(
        '/* Сгенерировано build.py из data/*.json — не редактировать вручную */\nwindow.BRO=' +
        json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n')

OLD_PAGES = {  # старые адреса OpenCart -> новые страницы
    'govyadina': 'catalog.html?cat=beef', 'katalog/govyadina': 'catalog.html?cat=beef',
    'baranina': 'catalog.html?cat=lamb', 'krolik': 'catalog.html?cat=rabbit',
    'ptica': 'catalog.html?cat=poultry', 'ptica/kurica': 'catalog.html?cat=poultry', 'ptica/utka': 'catalog.html?cat=poultry',
    'ptica/indejka': 'catalog.html?cat=poultry', 'ptica/perepela': 'catalog.html?cat=poultry',
    'kurica': 'catalog.html?cat=poultry', 'utka': 'catalog.html?cat=poultry', 'indejka': 'catalog.html?cat=poultry', 'perepela': 'catalog.html?cat=poultry',
    'miksy': 'catalog.html?cat=mix', 'miksy-bez-ovoshej': 'catalog.html?cat=mix', 'miksy-s-ovoshami': 'catalog.html?cat=mix',
    'miksy/miksy-bez-ovoshej': 'catalog.html?cat=mix', 'miksy/miksy-s-ovoshami': 'catalog.html?cat=mix',
    'lyuks': 'catalog.html?cat=premium', 'subprodukty': 'catalog.html?cat=offal', 'farsh': 'catalog.html?cat=farsh',
    'suhoj-korm': 'catalog.html?cat=treats', 'ekonom': 'catalog.html?cat=econom', 'opt-ot-100-kg': 'catalog.html',
    'o-nas': 'about.html', 'oplata-dostavka': 'delivery.html', 'faq': 'delivery.html', 'uslugi': 'index.html', 'privacy': 'privacy.html',
}

def write_redirects():
    """Заглушки по старым адресам: поисковик и закладки клиентов попадают на новые страницы."""
    targets = dict(OLD_PAGES)
    for p in ALL_PRODUCTS:
        old = (p.get('old_url') or '').replace(SITE['base_url'], '').strip('/')
        if old: targets[old] = (f'catalog.html?cat={p["cat"]}' if p['cat'] in CAT_NAME else 'catalog.html') if p.get('hidden') else f'p/{p["slug"]}.html'
    for old, new in targets.items():
        old = urllib.parse.unquote(old)
        r = '../' * (old.count('/') + 1)
        out = os.path.join(DIST, old, 'index.html')
        if os.path.exists(out): continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'w', encoding='utf-8').write(
            f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Страница переехала</title>'
            f'<meta name="robots" content="noindex"><link rel="canonical" href="{SITE["base_url"]}{new}">'
            f'<meta http-equiv="refresh" content="0; url={r}{new}"><script>location.replace("{r}{new}")</script></head>'
            f'<body><p>Страница переехала: <a href="{r}{new}">{SITE["base_url"]}{new}</a></p></body></html>')
    return len(targets)

def write_seo():
    base = SITE['base_url']
    urls = ''.join(f'<url><loc>{base}{p if p != "index.html" else ""}</loc></url>' for p in PAGES if p not in ('404.html', 'cart.html'))
    open(os.path.join(DIST, 'sitemap.xml'), 'w').write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    robots = 'User-agent: *\nDisallow: /\n' if PREVIEW else f'User-agent: *\nDisallow: /cart.html\nSitemap: {base}sitemap.xml\n'
    open(os.path.join(DIST, 'robots.txt'), 'w').write(robots)

def write_admin_demo():
    """Показ на GitHub Pages: админка без сервера (window.BRO_DEMO) с данными сайта в admin/state.json."""
    out = os.path.join(DIST, 'admin'); os.makedirs(out, exist_ok=True)
    src = open(os.path.join(ROOT, 'admin/index.html'), encoding='utf-8').read()
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(
        src.replace('<!--BRO_DEMO-->', '<script>window.BRO_DEMO = true;</script>', 1))
    state = {'products': ALL_PRODUCTS, 'cats': [[k, n] for k, n, _ in CATS], 'slides': SITE.get('slides', []),
             'icons': ['home', 'gift', 'truck', 'leaf', 'snow', 'wallet', 'chat', 'clock', 'pin'], 'hit_max': HIT_MAX}
    open(os.path.join(out, 'state.json'), 'w', encoding='utf-8').write(json.dumps(state, ensure_ascii=False))

def main():
    if os.path.exists(DIST): shutil.rmtree(DIST)
    shutil.copytree(os.path.join(ROOT, 'static'), os.path.join(DIST, 'static'))
    build_home(); build_catalog(); build_cart(); build_delivery(); build_about(); build_hotel(); build_privacy(); build_404()
    for p in PRODUCTS: build_product(p)
    write_data_js(); write_seo()
    n_redirects = write_redirects()
    open(os.path.join(DIST, '.nojekyll'), 'w').close()
    if PREVIEW: write_admin_demo()
    print(f'Готово: {len(PAGES)} страниц, {len(PRODUCTS)} товаров, {n_redirects} переадресаций со старых адресов -> {DIST}')

if __name__ == '__main__':
    main()
