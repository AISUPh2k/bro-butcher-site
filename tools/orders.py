"""Приём заказов с сайта: проверка, пересчёт цен по products.json, номер, журнал и письмо-накладная.

Настройки почты — orders.config.json рядом с build.py (образец: orders.config.example.json):
  "mode": "smtp"   — отправлять письмо через SMTP (Яндекс/Mail.ru: пароль приложения, не основной);
  "mode": "outbox" — не отправлять, а складывать письма в orders/outbox/*.eml (для проверки).
Журнал заказов: orders/<год>/<номер>.json. Это персональные данные клиентов — в dist/ не попадают.
Только stdlib + fpdf2 для PDF-накладной во вложении (нет fpdf2 — письмо уходит без PDF).
"""
import datetime, html, json, os, re, smtplib, ssl, threading, time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDERS = os.environ.get('BRO_ORDERS_DIR') or os.path.join(ROOT, 'orders')
CONFIG = os.environ.get('BRO_ORDERS_CONFIG') or os.path.join(ROOT, 'orders.config.json')
LOCK = threading.Lock()
RATE = {}  # ip -> [время заказов]
RATE_MAX, RATE_WINDOW = 5, 600
MSK = datetime.timezone(datetime.timedelta(hours=3), 'MSK')  # время в заказах — московское, где бы ни стоял сервер


class OrderError(Exception):
    pass


def rub(n):
    return f'{n:,}'.replace(',', ' ') + ' ₽'


def fmt_phone(raw):
    """Строго +7 и 10 цифр (11 цифр вместе с 7). Иначе — None."""
    raw = raw.strip()
    d = re.sub(r'\D', '', raw)
    if not raw.startswith('+7') or len(d) != 11: return None, None
    d = d[1:]
    return f'+7 ({d[:3]}) {d[3:6]}-{d[6:8]}-{d[8:]}', '+7' + d


def clean(v, maxlen, multiline=False):
    v = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(v or ''))
    if not multiline: v = re.sub(r'\s+', ' ', v)  # перенос строки в имени сломал бы тему письма
    return v.strip()[:maxlen]


def rate_ok(ip):
    now = time.time()
    if len(RATE) > 5000:
        for k in [k for k, v in RATE.items() if not v or now - v[-1] > RATE_WINDOW]: del RATE[k]
    hits = [t for t in RATE.get(ip, []) if now - t < RATE_WINDOW]
    RATE[ip] = hits
    if len(hits) >= RATE_MAX: return False
    hits.append(now)
    return True


def build_order(d, products, site):
    """Проверяет заявку и пересчитывает суммы по ценам из products.json (цены из браузера не используются)."""
    if not isinstance(d, dict): raise OrderError('Неверный запрос')
    if d.get('website'): raise OrderError('Неверный запрос')  # скрытое поле-ловушка для ботов
    name, address, comment = clean(d.get('name'), 80), clean(d.get('address'), 300), clean(d.get('comment'), 1000, multiline=True)
    phone, phone_raw = fmt_phone(clean(d.get('phone'), 40))
    if not phone: raise OrderError('Телефон должен начинаться с +7 и содержать 11 цифр')
    if len(name) < 2 or len(address) < 5:
        raise OrderError('Заполните имя, телефон и адрес')
    if not d.get('consent'): raise OrderError('Нужно согласие на обработку персональных данных')
    zone = 'out' if d.get('zone') == 'out' else 'mkad'
    by = {p['slug']: p for p in products}
    items, problems = [], []
    raw = d.get('items')
    if not isinstance(raw, list) or not 1 <= len(raw) <= 60: raise OrderError('Корзина пуста')
    for it in raw:
        if not isinstance(it, dict): raise OrderError('Неверный запрос')
        p = by.get(str(it.get('s')))
        label = str(it.get('o'))
        try: q = int(it.get('q'))
        except (TypeError, ValueError): q = 0
        price = next((pr for l, pr in p['options'] if l == label), None) if p else None
        if not p or p.get('hidden') or 'opt' in p['tags'] or price is None or not 1 <= q <= 99:
            problems.append(p['name'] if p else 'товар'); continue
        if not p['in_stock']:
            problems.append(p['name']); continue
        items.append({'slug': p['slug'], 'name': p['name'], 'option': label, 'qty': q, 'price': price, 'sum': price * q})
    if problems:
        raise OrderError('Этих позиций уже нет в продаже или изменилась фасовка — уберите их из корзины: ' + ', '.join(problems))
    dl = site['delivery']
    goods = sum(i['sum'] for i in items)
    if goods < dl['min_order']: raise OrderError(f'Минимальный заказ — {rub(dl["min_order"])}')
    fee = 0 if goods >= dl['free_from'] else dl['fee']
    client_total = d.get('total')
    return {
        'name': name, 'phone': phone, 'phone_raw': phone_raw, 'address': address, 'zone': zone, 'comment': comment,
        'items': items, 'goods': goods, 'fee': fee, 'total': goods + fee, 'per_km': dl['outside_per_km'] if zone == 'out' else 0,
        'window': dl['window'], 'payment': site.get('payment', 'Наличными после получения'),
        'price_changed': isinstance(client_total, (int, float)) and int(client_total) != goods + fee,
    }


def next_number():
    os.makedirs(ORDERS, exist_ok=True)
    path = os.path.join(ORDERS, 'counter.txt')
    try: n = int(open(path).read().strip()) + 1
    except (OSError, ValueError): n = 1
    with open(path + '.tmp', 'w') as f: f.write(str(n))
    os.replace(path + '.tmp', path)
    return n


def save(order):
    d = os.path.join(ORDERS, order['created'][:4]); os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f'{order["number"]}.json')
    with open(path + '.tmp', 'w', encoding='utf-8') as f: json.dump(order, f, ensure_ascii=False, indent=1)
    os.replace(path + '.tmp', path)


STATUSES = ('new', 'done', 'cancelled')  # в обработке / выполнен / отменён


def all_orders(limit=500):
    """Журнал для админки: новые сверху."""
    out = []
    if not os.path.isdir(ORDERS): return out
    for year in sorted((d for d in os.listdir(ORDERS) if d.isdigit()), reverse=True):
        for f in os.listdir(os.path.join(ORDERS, year)):
            if f.endswith('.json'):
                try: out.append(json.load(open(os.path.join(ORDERS, year, f), encoding='utf-8')))
                except (OSError, ValueError): pass
    out.sort(key=lambda o: o.get('number', 0), reverse=True)
    return out[:limit]


def find(number):
    for year in (d for d in os.listdir(ORDERS) if d.isdigit()) if os.path.isdir(ORDERS) else ():
        path = os.path.join(ORDERS, year, f'{int(number)}.json')
        if os.path.exists(path): return json.load(open(path, encoding='utf-8'))
    return None


def set_status(number, status):
    if status not in STATUSES: raise OrderError('Неизвестный статус')
    with LOCK:
        o = find(number)
        if not o: raise OrderError('Заказ не найден')
        o['status'] = status
        o['status_at'] = datetime.datetime.now(MSK).isoformat(timespec='seconds')
        save(o)
    return o


# ---------------------------------------------------------------- письмо
def total_text(o):
    return ('от ' if o['zone'] == 'out' else '') + rub(o['total'])


def delivery_text(o):
    t = rub(o['fee']) if o['fee'] else 'бесплатно'
    return t + (f' + {o["per_km"]} ₽/км за МКАД' if o['zone'] == 'out' else '')


def mail_text(o):
    out = [f'Заказ №{o["number"]} от {o["created_human"]}', '',
           f'Клиент: {o["name"]}', f'Телефон: {o["phone"]}', f'Адрес: {o["address"]}' + (' (за МКАД)' if o['zone'] == 'out' else ''), '']
    for n, i in enumerate(o['items'], 1):
        out.append(f'{n}. {i["name"]} — {i["option"]} × {i["qty"]} = {rub(i["sum"])}')
    out += ['', f'Товары: {rub(o["goods"])}', f'Доставка: {delivery_text(o)}', f'Итого: {total_text(o)}', f'Оплата: {o["payment"]}']
    if o['comment']: out += ['', f'Комментарий: {o["comment"]}']
    return '\n'.join(out).replace(' ', ' ')


def mail_html(o):
    """Накладная на один лист A4. Стили инлайном: почтовые клиенты часто выкидывают <style>."""
    e = html.escape
    td = 'padding:7px 8px;border-bottom:1px solid #d9cfbf;vertical-align:top;'
    rows = ''.join(
        f'<tr><td style="{td}color:#86735f">{n}</td><td style="{td}"><b>{e(i["name"])}</b></td>'
        f'<td style="{td}white-space:nowrap">{e(i["option"])}</td><td style="{td}text-align:center;font-size:17px"><b>{i["qty"]}</b></td>'
        f'<td style="{td}text-align:right;white-space:nowrap">{rub(i["price"])}</td><td style="{td}text-align:right;white-space:nowrap"><b>{rub(i["sum"])}</b></td>'
        f'<td style="{td}text-align:center"><span style="display:inline-block;width:16px;height:16px;border:1.5px solid #3b2a20;border-radius:3px"></span></td></tr>'
        for n, i in enumerate(o['items'], 1))
    th = 'padding:6px 8px;border-bottom:2px solid #3b2a20;text-align:left;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#6b5a47;'
    comment = (f'<div style="margin-top:14px;padding:10px 12px;border:1.5px solid #b08d57;border-radius:6px;background:#faf5ea">'
               f'<div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#8a6b3c">Комментарий клиента</div>'
               f'<div style="margin-top:4px;font-size:15px;white-space:pre-wrap">{e(o["comment"])}</div></div>') if o['comment'] else ''
    zone = ' <span style="color:#a4243b;font-weight:bold">· за МКАД</span>' if o['zone'] == 'out' else ''
    note = ('<p style="margin:10px 0 0;font-size:12px;color:#a4243b">Цены на сайте изменились, пока клиент оформлял заказ — '
            'суммы в накладной пересчитаны по текущим ценам.</p>') if o['price_changed'] else ''
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Заказ №{o["number"]}</title>
<style>@page{{size:A4;margin:12mm}} @media print{{body{{background:#fff!important}} .sheet{{border:0!important;box-shadow:none!important;padding:0!important}}}}</style></head>
<body style="margin:0;padding:16px;background:#efe8da;font-family:Arial,Helvetica,sans-serif;color:#3b2a20">
<div class="sheet" style="max-width:720px;margin:0 auto;background:#fff;border:1px solid #d9cfbf;border-radius:8px;padding:24px 28px">
 <table role="presentation" style="width:100%;border-collapse:collapse"><tr>
  <td style="vertical-align:top"><div style="font-size:26px;font-weight:bold;letter-spacing:.04em;color:#6e2430">БРО</div>
   <div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#86735f">мясная лавка · накладная</div></td>
  <td style="vertical-align:top;text-align:right"><div style="font-size:24px;font-weight:bold">Заказ №{o["number"]}</div>
   <div style="font-size:13px;color:#6b5a47">{e(o["created_human"])}</div></td></tr></table>

 <div style="margin-top:18px;padding:14px 16px;background:#f3ede0;border-radius:6px">
  <div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#86735f">Клиент</div>
  <div style="margin-top:2px;font-size:18px"><b>{e(o["name"])}</b></div>
  <div style="margin-top:4px;font-size:26px;font-weight:bold;letter-spacing:.02em"><a href="tel:{e(o["phone_raw"])}" style="color:#3b2a20;text-decoration:none">{e(o["phone"])}</a></div>
  <div style="margin-top:8px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#86735f">Адрес доставки</div>
  <div style="margin-top:2px;font-size:16px">{e(o["address"])}{zone}</div>
  <div style="margin-top:6px;font-size:13px;color:#6b5a47">Доставка {e(o["window"])} · {e(o["payment"])}</div>
 </div>
 {comment}

 <table style="width:100%;border-collapse:collapse;margin-top:18px;font-size:14px">
  <thead><tr><th style="{th}">№</th><th style="{th}">Товар</th><th style="{th}">Фасовка</th><th style="{th}text-align:center">Кол-во</th>
   <th style="{th}text-align:right">Цена</th><th style="{th}text-align:right">Сумма</th><th style="{th}text-align:center">✓</th></tr></thead>
  <tbody>{rows}</tbody>
 </table>

 <table role="presentation" style="width:100%;border-collapse:collapse;margin-top:12px;font-size:14px"><tr><td></td><td style="width:280px">
  <table role="presentation" style="width:100%;border-collapse:collapse">
   <tr><td style="padding:3px 0;color:#6b5a47">Товары</td><td style="padding:3px 0;text-align:right">{rub(o["goods"])}</td></tr>
   <tr><td style="padding:3px 0;color:#6b5a47">Доставка</td><td style="padding:3px 0;text-align:right">{e(delivery_text(o))}</td></tr>
   <tr><td style="padding:8px 0 0;border-top:2px solid #3b2a20;font-size:16px"><b>Итого к оплате</b></td>
       <td style="padding:8px 0 0;border-top:2px solid #3b2a20;text-align:right;font-size:20px"><b>{total_text(o)}</b></td></tr>
  </table></td></tr></table>
 {note}
 <table role="presentation" style="width:100%;border-collapse:collapse;margin-top:28px;font-size:12px;color:#6b5a47"><tr>
  <td>Собрал: ____________________</td><td style="text-align:right">Получил: ____________________</td></tr></table>
</div></body></html>'''


# ---------------------------------------------------------------- PDF-накладная
FONTS = os.path.join(ROOT, 'tools/fonts')
INK, SOFT, FAINT, BURG, BRASS, CREAM, LINE = (59, 42, 32), (107, 90, 71), (134, 115, 95), (110, 36, 48), (176, 141, 87), (243, 237, 224), (217, 207, 191)


def mail_pdf(o):
    """Накладная A4 для печати одного заказа (вложение к письму). None — нет fpdf2."""
    return orders_pdf([o])


def orders_pdf(lst):
    """Накладные A4 одним файлом: каждый заказ с нового листа — телефон крупно, клеточки «собрано». None — нет fpdf2."""
    try:
        from fpdf import FPDF
        from fpdf.enums import TableBordersLayout
    except ImportError:
        return None
    single = len(lst) == 1
    class Sheet(FPDF):
        cur, start = None, 1
        def footer(self):  # номер заказа на каждом листе — чтобы листы разных заказов не перепутались
            self.set_y(-10); self.set_font('golos', '', 8); self.set_text_color(*FAINT)
            k = self.page_no() - self.start + 1
            self.cell(0, 5, f'Заказ №{self.cur["number"]} · стр. {k}' + (' из {nb}' if single else ''), align='R')
    pdf = Sheet(format='A4', unit='mm')
    pdf.set_margins(14, 12, 14); pdf.set_auto_page_break(True, 14)
    for fam, style, f in (('golos', '', 'GolosText-400'), ('golos', 'B', 'GolosText-600'),
                          ('oswald', '', 'Oswald-500'), ('oswald', 'B', 'Oswald-700'), ('rub', '', 'Rub-Regular'), ('rub', 'B', 'Rub-Bold'), ('box', '', 'Box')):
        pdf.add_font(fam, style, os.path.join(FONTS, f + '.ttf'))
    pdf.set_fallback_fonts(['rub', 'box'], exact_match=False)  # знаки ₽ и □
    pdf.set_title('Заказ №' + ', '.join(str(o['number']) for o in lst)); pdf.set_author('Мясная лавка БРО')

    def draw(o):
        W = pdf.epw
        t = lambda v: str(v).replace('\u00a0', ' ')

        def label(text, color=FAINT):
            pdf.set_font('golos', '', 7.5); pdf.set_text_color(*color); pdf.set_char_spacing(0.6)
            pdf.cell(0, 4, text.upper(), new_x='LMARGIN', new_y='NEXT'); pdf.set_char_spacing(0)

        # шапка
        y0 = pdf.get_y()
        pdf.set_font('oswald', 'B', 22); pdf.set_text_color(*BURG); pdf.cell(60, 9, 'БРО')
        pdf.set_font('oswald', 'B', 20); pdf.set_text_color(*INK); pdf.cell(0, 9, f'Заказ №{o["number"]}', align='R', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('golos', '', 7.5); pdf.set_text_color(*FAINT); pdf.set_char_spacing(0.6); pdf.cell(60, 5, 'МЯСНАЯ ЛАВКА · НАКЛАДНАЯ'); pdf.set_char_spacing(0)
        pdf.set_font('golos', '', 9.5); pdf.set_text_color(*SOFT); pdf.cell(0, 5, o['created_human'], align='R', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(5)

        # клиент
        box_y = pdf.get_y(); pdf.set_x(pdf.l_margin + 5); pdf.set_y(box_y + 4)
        inner = lambda: pdf.set_x(pdf.l_margin + 5)
        def block():
            inner(); label('Клиент'); inner()
            pdf.set_font('golos', 'B', 13); pdf.set_text_color(*INK); pdf.multi_cell(W - 10, 6.5, t(o['name']), new_x='LMARGIN', new_y='NEXT')
            inner(); pdf.set_font('oswald', 'B', 24); pdf.cell(W - 10, 11, o['phone'], link=f'tel:{o["phone_raw"]}', new_x='LMARGIN', new_y='NEXT')
            pdf.ln(1); inner(); label('Адрес доставки'); inner()
            pdf.set_font('golos', '', 11.5); pdf.set_text_color(*INK)
            pdf.multi_cell(W - 10, 6, t(o['address']) + ('  · за МКАД' if o['zone'] == 'out' else ''), new_x='LMARGIN', new_y='NEXT')
            inner(); pdf.set_font('golos', '', 9); pdf.set_text_color(*SOFT)
            pdf.multi_cell(W - 10, 5, t(f'Доставка {o["window"]} · {o["payment"]}'), new_x='LMARGIN', new_y='NEXT')
        with pdf.offset_rendering() as dummy:  # сначала меряем высоту, потом рисуем фон
            dummy.set_y(box_y + 4); block(); h = dummy.get_y() - box_y + 4
        pdf.set_fill_color(*CREAM); pdf.rect(pdf.l_margin, box_y, W, h, style='F', round_corners=True, corner_radius=2)
        pdf.set_y(box_y + 4); block(); pdf.set_y(box_y + h + 4)

        # комментарий
        if o['comment']:
            cy = pdf.get_y()
            def cblock():
                inner(); label('Комментарий клиента', (138, 107, 60)); inner()
                pdf.set_font('golos', '', 11); pdf.set_text_color(*INK); pdf.multi_cell(W - 10, 5.5, t(o['comment']), new_x='LMARGIN', new_y='NEXT')
            with pdf.offset_rendering() as dummy:
                dummy.set_y(cy + 3); cblock(); ch = dummy.get_y() - cy + 3
            pdf.set_draw_color(*BRASS); pdf.set_line_width(0.4)
            pdf.rect(pdf.l_margin, cy, W, ch, style='D', round_corners=True, corner_radius=2)
            pdf.set_y(cy + 3); cblock(); pdf.set_y(cy + ch + 4)

        # товары
        pdf.ln(2); pdf.set_draw_color(*LINE); pdf.set_line_width(0.25)
        pdf.set_font('golos', '', 10); pdf.set_text_color(*INK); pdf.set_fill_color(255, 255, 255)
        from fpdf.fonts import FontFace
        hstyle = FontFace(family='golos', emphasis='', size_pt=7.5, color=SOFT)
        with pdf.table(col_widths=(7, 74, 20, 15, 22, 24, 12), text_align=('LEFT', 'LEFT', 'LEFT', 'CENTER', 'RIGHT', 'RIGHT', 'CENTER'),
                       borders_layout=TableBordersLayout.HORIZONTAL_LINES, headings_style=hstyle, line_height=6.5,
                       padding=(1.6, 1.2), first_row_as_headings=True) as table:
            row = table.row()
            for h_ in ('№', 'ТОВАР', 'ФАСОВКА', 'КОЛ-ВО', 'ЦЕНА', 'СУММА', 'СОБР.'): row.cell(h_)
            for n, i in enumerate(o['items'], 1):
                row = table.row()
                row.cell(str(n), style=FontFace(color=FAINT))
                row.cell(t(i['name']), style=FontFace(emphasis='BOLD'))
                row.cell(t(i['option']))
                row.cell(str(i['qty']), style=FontFace(emphasis='BOLD', size_pt=12))
                row.cell(t(rub(i['price'])))
                row.cell(t(rub(i['sum'])), style=FontFace(emphasis='BOLD'))
                row.cell('□', style=FontFace(size_pt=15, color=INK))  # клеточка для отметки при сборке
        pdf.ln(3)

        # итог
        x = pdf.l_margin + W - 80
        def trow(k, v, big=False):
            pdf.set_x(x)
            pdf.set_font('golos', 'B' if big else '', 12 if big else 10); pdf.set_text_color(*(INK if big else SOFT)); pdf.cell(40, 7 if big else 6, k)
            pdf.set_font('oswald' if big else 'golos', 'B' if big else '', 17 if big else 10); pdf.set_text_color(*INK)
            pdf.cell(40, 7 if big else 6, t(v), align='R', new_x='LMARGIN', new_y='NEXT')
        trow('Товары', rub(o['goods'])); trow('Доставка', delivery_text(o))
        pdf.set_draw_color(*INK); pdf.set_line_width(0.5); pdf.line(x, pdf.get_y() + 1, x + 80, pdf.get_y() + 1); pdf.ln(2.5)
        trow('Итого к оплате', total_text(o), big=True)
        if o['price_changed']:
            pdf.ln(2); pdf.set_font('golos', '', 8.5); pdf.set_text_color(164, 36, 59)
            pdf.multi_cell(0, 4.5, 'Цены на сайте изменились, пока клиент оформлял заказ — суммы пересчитаны по текущим ценам.', new_x='LMARGIN', new_y='NEXT')

        # подписи
        pdf.ln(12); pdf.set_font('golos', '', 9.5); pdf.set_text_color(*SOFT)
        pdf.cell(W / 2, 6, 'Собрал: ______________________'); pdf.cell(W / 2, 6, 'Получил: ______________________', align='R')

    for o in lst:
        pdf.add_page()  # footer прошлого листа уже отрисован — теперь переключаемся на новый заказ
        pdf.cur, pdf.start = o, pdf.page_no()
        draw(o)
    return bytes(pdf.output())


def make_message(o, cfg):
    m = EmailMessage()
    m['Subject'] = f'Заказ №{o["number"]} — {total_text(o)} — {o["name"]}, {o["phone"]}'.replace(' ', ' ')
    m['From'] = formataddr(('Сайт БРО', cfg['from']))
    m['To'] = ', '.join(cfg['to'])
    m['Message-ID'] = make_msgid(domain=cfg['from'].split('@')[-1])
    m.set_content(mail_text(o))
    m.add_alternative(mail_html(o), subtype='html')
    pdf = mail_pdf(o)
    if pdf: m.add_attachment(pdf, maintype='application', subtype='pdf', filename=f'Заказ-{o["number"]}.pdf')
    else: print('orders: fpdf2 не установлен — письмо без PDF (pip install fpdf2)', flush=True)
    return m


def send(o, cfg):
    m = make_message(o, cfg)
    if cfg.get('mode') == 'outbox':
        d = os.path.join(ORDERS, 'outbox'); os.makedirs(d, exist_ok=True)
        open(os.path.join(d, f'{o["number"]}.eml'), 'wb').write(bytes(m))
        head = (f'<div style="font:13px Arial;max-width:720px;margin:0 auto 12px;padding:10px 14px;background:#fff;border-radius:6px">'
                f'<b>Тема:</b> {html.escape(m["Subject"])}<br><b>От:</b> {html.escape(m["From"])}<br><b>Кому:</b> {html.escape(m["To"])}</div>')
        preview = mail_html(o).replace('<div class="sheet"', head + '<div class="sheet"', 1)  # то же письмо, но открывается в браузере
        open(os.path.join(d, f'{o["number"]}.html'), 'w', encoding='utf-8').write(preview)
        for part in m.iter_attachments():
            open(os.path.join(d, part.get_filename()), 'wb').write(part.get_content())
        return
    host, port = cfg['smtp_host'], int(cfg.get('smtp_port', 465))
    if cfg.get('security', 'ssl') == 'ssl':
        s = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context())
    else:
        s = smtplib.SMTP(host, port, timeout=20)
        if cfg.get('security') == 'starttls': s.starttls(context=ssl.create_default_context())
    with s:
        if cfg.get('user'): s.login(cfg['user'], cfg['password'])
        s.send_message(m)


def load_config():
    try: cfg = json.load(open(CONFIG, encoding='utf-8'))
    except OSError: raise OrderError('Приём заказов не настроен (нет orders.config.json)')
    if isinstance(cfg.get('to'), str): cfg['to'] = [cfg['to']]
    return cfg


def place(d, ip):
    """Главная точка входа: проверить, пронумеровать, сохранить, отправить. Возвращает заказ."""
    root = ROOT
    products = json.load(open(os.path.join(root, 'data/products.json'), encoding='utf-8'))
    site = json.load(open(os.path.join(root, 'data/site.json'), encoding='utf-8'))
    o = build_order(d, products, site)
    cfg = load_config()
    with LOCK:
        if not rate_ok(ip): raise OrderError('Слишком много заказов подряд. Позвоните нам, пожалуйста')
        now = datetime.datetime.now(MSK)
        o.update(number=next_number(), created=now.isoformat(timespec='seconds'),
                 created_human=now.strftime('%d.%m.%Y %H:%M'), status='new', mail='pending')
        save(o)
    try:
        send(o, cfg); o['mail'] = 'sent'
    except Exception as ex:  # заказ уже в журнале; клиенту предложим WhatsApp
        o['mail'] = 'failed'; o['mail_error'] = f'{type(ex).__name__}: {ex}'[:300]
    save(o)
    return o
