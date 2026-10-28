#!/usr/bin/env python3
"""Админка сайта БРО: правка товаров (цены, фасовки, описание, фото) и объявлений на главной.

    python3 tools/admin_server.py --password   # задать пароль (один раз)
    python3 tools/admin_server.py              # http://127.0.0.1:8100/admin/  (сайт — http://127.0.0.1:8100/)

Каждое сохранение пишет data/*.json, кладёт прошлую версию в data/backups/ и пересобирает сайт (build.py).
Если сборка упала — данные откатываются. Для фото нужен Pillow (pip install pillow).
Только stdlib + Pillow, чтобы потом перенести тот же API в облачную функцию.
"""
import base64, datetime, getpass, hashlib, hmac, http.server, io, json, mimetypes, os, re, secrets
import shutil, subprocess, sys, threading, time, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, DIST, ADMIN = (os.path.join(ROOT, d) for d in ('data', 'dist', 'admin'))
PROD_IMG = os.path.join(ROOT, 'static/img/products')
BACKUPS = os.path.join(DATA, 'backups')
SECRET = os.environ.get('BRO_ADMIN_SECRET') or os.path.join(ROOT, 'admin.secret.json')
KEEP_BACKUPS = 60
SESSION_TTL = 12 * 3600
MAX_BODY = 20 * 1024 * 1024

sys.path.insert(0, ROOT)
import build  # noqa: E402  — только константы (CATS, ICONS); сборку запускаем отдельным процессом
import orders  # noqa: E402  (tools/ уже в sys.path как каталог скрипта)

CATS = [[k, n] for k, n, _ in build.CATS]
CAT_KEYS = {k for k, _ in CATS}
ICON_CHOICES = ['home', 'gift', 'truck', 'leaf', 'snow', 'wallet', 'chat', 'clock', 'pin']
LOCK = threading.Lock()
SESSIONS = {}  # token -> срок
FAILS = {'n': 0, 'until': 0.0}

# ---------------------------------------------------------------- пароль
def hash_pw(pw, salt=None):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt, 240_000)
    return {'salt': base64.b64encode(salt).decode(), 'hash': base64.b64encode(dk).decode(), 'iter': 240_000}

def check_pw(pw):
    try: s = json.load(open(SECRET, encoding='utf-8'))
    except OSError: return False
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode(), base64.b64decode(s['salt']), s['iter'])
    return hmac.compare_digest(base64.b64encode(dk).decode(), s['hash'])

def set_password(pw):
    with open(SECRET, 'w', encoding='utf-8') as f: json.dump(hash_pw(pw), f)
    os.chmod(SECRET, 0o600)

# ---------------------------------------------------------------- данные
def load(name):
    return json.load(open(os.path.join(DATA, name), encoding='utf-8'))

def save_and_build(changes):
    """changes: {имя файла: новые данные}. Бэкап -> запись -> сборка; при ошибке сборки откат."""
    os.makedirs(BACKUPS, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    old = {}
    for name, value in changes.items():
        path = os.path.join(DATA, name)
        old[name] = open(path, encoding='utf-8').read()
        shutil.copy2(path, os.path.join(BACKUPS, f'{name[:-5]}-{stamp}.json'))
        write_atomic(path, json.dumps(value, ensure_ascii=False, indent=1) + '\n')
    for prefix in {n[:-5] for n in changes}:
        files = sorted(f for f in os.listdir(BACKUPS) if f.startswith(prefix + '-'))
        for f in files[:-KEEP_BACKUPS]: os.remove(os.path.join(BACKUPS, f))
    ok, log = run_build()
    if not ok:
        for name, text in old.items(): write_atomic(os.path.join(DATA, name), text)
        run_build()
    return ok, log

def write_atomic(path, text):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: f.write(text)
    os.replace(tmp, path)

def run_build():
    env = dict(os.environ, BRO_ORDER_API='/api/order')  # корзина шлёт заказ сюда, а не в WhatsApp
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'build.py')], capture_output=True, text=True, timeout=120, env=env)
    return r.returncode == 0, (r.stdout + r.stderr).strip()[-2000:]

# ---------------------------------------------------------------- проверка ввода
class Bad(Exception): pass

def text(v, field, maxlen, required=False):
    if v is None: v = ''
    if not isinstance(v, str): raise Bad(f'{field}: ожидается текст')
    v = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', v).strip()
    if required and not v: raise Bad(f'Заполните поле «{field}»')
    if len(v) > maxlen: raise Bad(f'«{field}» длиннее {maxlen} символов')
    return v

def lines(v, field, maxn, maxlen):
    if isinstance(v, str): v = v.split('\n')
    if not isinstance(v, list): raise Bad(f'{field}: неверный формат')
    out = [text(x, field, maxlen) for x in v]
    out = [x for x in out if x]
    if len(out) > maxn: raise Bad(f'«{field}»: не больше {maxn} строк')
    return out

def grams(label):
    m = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*(г|гр|кг)\.?\s*', label.lower())
    if not m: return None
    n = float(m.group(1).replace(',', '.'))
    return n * 1000 if m.group(2) == 'кг' else n

def clean_product(d, existing):
    p = dict(existing or {})
    p['name'] = text(d.get('name'), 'Название', 120, True)
    tags = [t for t in (d.get('tags') or []) if t in CAT_KEYS]
    if not tags: raise Bad('Отметьте хотя бы один раздел каталога')
    p['tags'] = list(dict.fromkeys(tags)); p['cat'] = p['tags'][0]
    opts = d.get('options') or []
    if not isinstance(opts, list) or not 1 <= len(opts) <= 10: raise Bad('Нужна хотя бы одна фасовка (не больше 10)')
    clean, seen = [], set()
    for o in opts:
        if not isinstance(o, (list, tuple)) or len(o) != 2: raise Bad('Фасовка: неверный формат')
        label = text(o[0], 'Фасовка', 24, True)
        try: price = int(str(o[1]).replace(' ', '').replace(' ', ''))
        except ValueError: raise Bad(f'Цена для «{label}» должна быть числом')
        if not 1 <= price <= 1_000_000: raise Bad(f'Проверьте цену для «{label}»')
        if label in seen: raise Bad(f'Фасовка «{label}» повторяется')
        seen.add(label); clean.append([label, price])
    if all(grams(l) is not None for l, _ in clean): clean.sort(key=lambda o: grams(o[0]))
    p['options'] = clean
    for k in ('in_stock', 'veg', 'hidden'): p[k] = bool(d.get(k))
    p['composition'] = lines(d.get('composition'), 'Состав', 40, 200)
    notes = d.get('notes') or ''
    if isinstance(notes, list): notes = '\n\n'.join(notes)
    p['notes'] = [text(x, 'Описание', 4000) for x in re.split(r'\n\s*\n', str(notes)) if x.strip()][:12]
    k = d.get('kbju') or {}
    kb = {key: text(str(k.get(key) or ''), 'КБЖУ', 8) for key in ('b', 'z', 'u', 'kcal')}
    for key, val in kb.items():
        if val and not re.fullmatch(r'\d+([.,]\d+)?', val): raise Bad('КБЖУ: только числа, например 18,5')
    p['kbju'] = kb if any(kb.values()) else None
    hit = bool(d.get('hit'))
    was_hit = bool(p.get('popular')) and p['popular'] <= build.HIT_MAX
    if hit and not was_hit:
        used = {x.get('popular') for x in load('products.json')}
        p['popular'] = next((i for i in range(1, build.HIT_MAX + 1) if i not in used), build.HIT_MAX)
    elif not hit and was_hit:
        p['popular'] = None
    p.setdefault('popular', None); p.setdefault('img', None); p.setdefault('old_url', '')
    return p

TR = dict(zip('абвгдеёзийклмнопрстуфхцы', 'abvgdeezijklmnoprstufhcy'))
TR.update({'ж': 'zh', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'})

def make_slug(name, taken):
    base = re.sub(r'[^a-z0-9]+', '-', ''.join(TR.get(c, c) for c in name.lower())).strip('-')[:60] or 'tovar'
    slug, i = base, 2
    while slug in taken: slug, i = f'{base}-{i}', i + 1
    return slug

LINK_RE = re.compile(r'(whatsapp|[a-z0-9_-]+\.html(\?[a-z0-9=&_-]*)?(#[a-z0-9_-]*)?|p/[a-z0-9-]+\.html|https://[^\s"<>]+)')

def clean_slides(items):
    if not isinstance(items, list) or len(items) > 8: raise Bad('Не больше 8 объявлений')
    out = []
    for n, d in enumerate(items, 1):
        f = lambda key, label, ml, req=False: text(d.get(key), f'{label} (объявление {n})', ml, req)
        s = {'off': bool(d.get('off')),
             'theme': d.get('theme') if d.get('theme') in ('olive', 'burgundy', 'light') else 'light',
             'eyebrow': f('eyebrow', 'Надпись сверху', 40), 'title': f('title', 'Заголовок', 90, True),
             'text': f('text', 'Текст', 260), 'button': f('button', 'Кнопка', 30, True),
             'link': f('link', 'Куда ведёт кнопка', 300, True)}
        if not LINK_RE.fullmatch(s['link']): raise Bad(f'Объявление {n}: неверная ссылка кнопки')
        if s['link'] == 'whatsapp': s['wa_text'] = f('wa_text', 'Текст для WhatsApp', 300)
        if d.get('art') == 'hotel': s['art'] = 'hotel'  # оформление «арка + печать + карточки» (слайд гостиницы)
        img = d.get('img') or ''
        if img:
            if not re.fullmatch(r'[a-z0-9-]+\.jpg', img) or not os.path.exists(os.path.join(PROD_IMG, img)):
                raise Bad(f'Объявление {n}: картинка не найдена')
            s['img'] = img
        else:
            s['icon'] = d.get('icon') if d.get('icon') in ICON_CHOICES else 'gift'
        until = d.get('until') or ''
        if until:
            try: datetime.date.fromisoformat(until)
            except ValueError: raise Bad(f'Объявление {n}: неверная дата')
            s['until'] = until
        out.append(s)
    return out

# ---------------------------------------------------------------- фото
def save_photo(raw, stem):
    try:
        from PIL import Image
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import images
    except ImportError:
        raise Bad('На сервере не установлен Pillow: pip install pillow')
    try:
        im = Image.open(io.BytesIO(raw)); im.load()
    except Exception:
        raise Bad('Не удалось открыть фото. Подойдут JPG, PNG или WebP')
    if im.size[0] < 300 or im.size[1] < 220: raise Bad('Фото слишком маленькое, нужно хотя бы 800×600')
    path = os.path.join(PROD_IMG, stem + '.jpg')
    images.fit(im, 800, 600).save(path, 'JPEG', quality=82, optimize=True, progressive=True)
    images.variants(path, PROD_IMG, stem, (400, 800))
    return stem + '.jpg'

# ---------------------------------------------------------------- HTTP
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'BRO-admin'

    def log_message(self, fmt, *a):
        if '/api/' in self.path: sys.stderr.write('%s %s\n' % (self.log_date_time_string(), fmt % a))

    def send(self, code, body=b'', ctype='application/json; charset=utf-8', extra=()):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        if self.path.startswith(('/admin', '/api')):
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Frame-Options', 'DENY')
        for k, v in extra: self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD': self.wfile.write(body)

    def token(self):
        for part in (self.headers.get('Cookie') or '').split(';'):
            k, _, v = part.strip().partition('=')
            if k == 'bro_admin': return v
        return ''

    def authed(self):
        t = self.token(); exp = SESSIONS.get(t)
        if not exp or exp < time.time():
            SESSIONS.pop(t, None); return False
        return True

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > MAX_BODY: raise Bad('Файл слишком большой (больше 20 МБ)')
        return self.rfile.read(n)

    def json_body(self):
        try: return json.loads(self.body() or b'{}')
        except ValueError: raise Bad('Неверный запрос')

    # -- статика: /admin/ — панель, остальное — собранный сайт для предпросмотра
    def do_HEAD(self): self.do_GET()

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path == '/api/state':
            if not self.authed(): return self.send(401, {'error': 'Войдите заново'})
            site = load('site.json')
            return self.send(200, {'products': load('products.json'), 'cats': CATS, 'slides': site.get('slides', []),
                                   'icons': ICON_CHOICES, 'hit_max': build.HIT_MAX})
        if url.path == '/api/session': return self.send(200, {'ok': self.authed()})
        if url.path == '/api/orders':
            if not self.authed(): return self.send(401, {'error': 'Войдите заново'})
            keep = ('number', 'created_human', 'name', 'phone', 'phone_raw', 'address', 'zone', 'comment', 'items',
                    'goods', 'fee', 'total', 'status', 'mail')
            return self.send(200, {'orders': [{k: o.get(k) for k in keep} for o in orders.all_orders()]})
        if url.path == '/api/orders/pdf':
            if not self.authed(): return self.send(401, b'login', 'text/plain; charset=utf-8')
            q = urllib.parse.parse_qs(url.query)
            try: o = orders.find(int((q.get('n') or ['0'])[0]))
            except ValueError: o = None
            if not o: return self.send(404, b'not found', 'text/plain')
            pdf = orders.mail_pdf(o)
            name = urllib.parse.quote(f'Заказ-{o["number"]}' + ('.pdf' if pdf else '.html'))
            disp = [('Content-Disposition', f"attachment; filename*=UTF-8''{name}")]
            if pdf: return self.send(200, pdf, 'application/pdf', disp)
            return self.send(200, orders.mail_html(o).encode(), 'text/html; charset=utf-8', disp)  # нет fpdf2 — HTML-накладная
        if url.path in ('/admin', '/admin/'): return self.static(ADMIN, 'index.html')
        if url.path.startswith('/admin/'): return self.static(ADMIN, url.path[len('/admin/'):])
        return self.static(DIST, url.path.lstrip('/'))

    def static(self, base, rel):
        rel = urllib.parse.unquote(rel)
        path = os.path.realpath(os.path.join(base, rel))
        if not path.startswith(os.path.realpath(base) + os.sep) and path != os.path.realpath(base):
            return self.send(404, b'not found', 'text/plain')
        if os.path.isdir(path): path = os.path.join(path, 'index.html')
        if not os.path.isfile(path):
            p404 = os.path.join(DIST, '404.html')
            return self.send(404, open(p404, 'rb').read() if base == DIST and os.path.exists(p404) else b'not found', 'text/html; charset=utf-8')
        ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        if ctype.startswith('text/') or ctype in ('application/javascript', 'application/json'): ctype += '; charset=utf-8'
        self.send(200, open(path, 'rb').read(), ctype)

    def do_POST(self):
        url = urllib.parse.urlsplit(self.path)
        # защита от подделки запросов с чужих страниц: только свой Origin и наш заголовок
        origin = self.headers.get('Origin')
        if self.headers.get('X-BRO') != '1' or (origin and urllib.parse.urlsplit(origin).netloc != self.headers.get('Host')):
            return self.send(403, {'error': 'Запрос отклонён'})
        try:
            if url.path == '/api/order': return self.order()
            if url.path == '/api/login': return self.login()
            if url.path == '/api/logout':
                SESSIONS.pop(self.token(), None)
                return self.send(200, {'ok': True}, extra=[('Set-Cookie', 'bro_admin=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict')])
            if not self.authed(): return self.send(401, {'error': 'Войдите заново'})
            with LOCK:
                if url.path == '/api/product': return self.product()
                if url.path == '/api/photo': return self.photo(urllib.parse.parse_qs(url.query))
                if url.path == '/api/slides': return self.slides()
                if url.path == '/api/orders/status':
                    d = self.json_body()
                    try: o = orders.set_status(int(d.get('number') or 0), d.get('status'))
                    except orders.OrderError as ex: raise Bad(str(ex))
                    return self.send(200, {'ok': True, 'status': o['status']})
            self.send(404, {'error': 'Нет такого действия'})
        except Bad as ex:
            self.send(400, {'error': str(ex)})

    def order(self):
        if int(self.headers.get('Content-Length') or 0) > 64 * 1024: raise Bad('Слишком большой заказ')
        try:
            o = orders.place(self.json_body(), self.client_address[0])
        except orders.OrderError as ex:
            return self.send(400, {'error': str(ex)})
        if o['mail'] != 'sent':
            sys.stderr.write(f'ЗАКАЗ {o["number"]}: письмо не ушло — {o.get("mail_error")}\n')
            return self.send(502, {'error': 'Не получилось отправить заказ', 'fallback': True})
        self.send(200, {'ok': True, 'number': o['number'], 'total': o['total'], 'out': o['zone'] == 'out'})

    def login(self):
        if FAILS['until'] > time.time(): return self.send(429, {'error': 'Слишком много попыток, подождите минуту'})
        pw = str(self.json_body().get('password') or '')
        if not check_pw(pw):
            FAILS['n'] += 1
            if FAILS['n'] >= 5: FAILS.update(n=0, until=time.time() + 60)
            time.sleep(0.8)
            return self.send(403, {'error': 'Неверный пароль'})
        FAILS['n'] = 0
        t = secrets.token_urlsafe(32); SESSIONS[t] = time.time() + SESSION_TTL
        # Secure — только когда сайт отдаётся по HTTPS (за прокси); в локальной сети и на localhost это обычный HTTP
        https = self.headers.get('X-Forwarded-Proto') == 'https' or os.environ.get('BRO_COOKIE_SECURE') == '1'
        cookie = f'bro_admin={t}; Path=/; Max-Age={SESSION_TTL}; HttpOnly; SameSite=Strict' + ('; Secure' if https else '')
        self.send(200, {'ok': True}, extra=[('Set-Cookie', cookie)])

    def product(self):
        d = self.json_body()
        products = load('products.json')
        by = {p['slug']: i for i, p in enumerate(products)}
        slug = d.get('slug')
        if slug:
            if slug not in by: raise Bad('Товар не найден — обновите страницу')
            p = clean_product(d, products[by[slug]]); products[by[slug]] = p
        else:
            p = clean_product(d, None)
            p['slug'] = make_slug(p['name'], set(by))
            products.append(p)
        ok, log = save_and_build({'products.json': products})
        if not ok: return self.send(500, {'error': 'Сайт не собрался, изменения отменены', 'log': log})
        self.send(200, {'ok': True, 'product': p, 'log': log})

    def photo(self, q):
        kind = (q.get('kind') or ['product'])[0]
        raw = self.body()
        if kind == 'slide':
            img = save_photo(raw, 'slide-' + secrets.token_hex(4))
            run_build()  # чтобы превью картинки открылось в админке; на главной она появится после сохранения объявлений
            return self.send(200, {'ok': True, 'img': img})
        slug = (q.get('slug') or [''])[0]
        products = load('products.json')
        p = next((x for x in products if x['slug'] == slug), None)
        if not p: raise Bad('Сначала сохраните товар, потом добавьте фото')
        p['img'] = save_photo(raw, slug)
        ok, log = save_and_build({'products.json': products})
        if not ok: return self.send(500, {'error': 'Сайт не собрался', 'log': log})
        self.send(200, {'ok': True, 'img': p['img'], 'v': int(time.time())})

    def slides(self):
        site = load('site.json')
        site['slides'] = clean_slides(self.json_body().get('slides'))
        ok, log = save_and_build({'site.json': site})
        if not ok: return self.send(500, {'error': 'Сайт не собрался, изменения отменены', 'log': log})
        self.send(200, {'ok': True, 'slides': site['slides']})

def main():
    if '--password' in sys.argv:
        pw = getpass.getpass('Новый пароль для админки: ')
        if len(pw) < 8: sys.exit('Пароль короче 8 символов')
        if getpass.getpass('Ещё раз: ') != pw: sys.exit('Пароли не совпали')
        set_password(pw); print('Пароль сохранён в', SECRET); return
    if not os.path.exists(SECRET): sys.exit('Сначала задайте пароль: python3 tools/admin_server.py --password')
    host = os.environ.get('BRO_ADMIN_HOST', '127.0.0.1'); port = int(os.environ.get('BRO_ADMIN_PORT', '8100'))
    ok, log = run_build()  # всегда: собрать корзину с приёмом заказов через этот сервер
    if not ok: sys.exit('Сайт не собрался:\n' + log)
    srv = http.server.ThreadingHTTPServer((host, port), Handler)
    print(f'Админка: http://{host}:{port}/admin/   сайт: http://{host}:{port}/')
    try: srv.serve_forever()
    except KeyboardInterrupt: pass

if __name__ == '__main__':
    main()
