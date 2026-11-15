"""Страница из dist/ одним самостоятельным HTML (CSS, шрифты, JS, картинки внутри) — переслать заказчице.
python3 tools/onefile.py dist index.html "ПП БРО — главная.html"   (ссылки на другие страницы в таком файле не работают)"""
import base64, mimetypes, os, re, sys

dist, page, out = sys.argv[1:]
base = os.path.dirname(os.path.join(dist, page))
MIME = {'.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.png': 'image/png'}

def data_uri(path):
    ext = os.path.splitext(path)[1].lower()
    return f'data:{MIME.get(ext) or mimetypes.guess_type(path)[0]};base64,' + base64.b64encode(open(path, 'rb').read()).decode()

def resolve(rel, start):
    return os.path.normpath(os.path.join(start, rel.split('?')[0].split('#')[0]))

html = open(os.path.join(dist, page), encoding='utf-8').read()

# стили со шрифтами
def css(m):
    p = resolve(m.group(1), base)
    text = open(p, encoding='utf-8').read()
    text = re.sub(r'url\(([^)"\']+)\)', lambda u: f'url({data_uri(resolve(u.group(1), os.path.dirname(p)))})', text)
    return f'<style>\n{text}\n</style>'
html = re.sub(r'<link rel="stylesheet" href="([^"]+)">', css, html)
html = re.sub(r'<link rel="preload"[^>]*>\n?', '', html)
html = re.sub(r'<link rel="icon" href="([^"]+)"', lambda m: f'<link rel="icon" href="{data_uri(resolve(m.group(1), base))}"', html)

# скрипты
html = re.sub(r'<script src="([^"]+)"( defer)?></script>',
              lambda m: '<script>\n' + open(resolve(m.group(1), base), encoding='utf-8').read().replace('</script', '<\\/script') + '\n</script>', html)

# картинки: <source srcset> убираем, в <img> оставляем одну встроенную картинку
html = re.sub(r'<source type="image/webp" srcset="[^"]*"[^>]*>', '', html)
def img(m):
    tag = m.group(0)
    src = re.search(r'src="([^"]+)"', tag)
    if not src or src.group(1).startswith(('data:', 'http')): return tag
    p = resolve(src.group(1), base)
    if not os.path.exists(p): return tag
    return tag.replace(src.group(0), f'src="{data_uri(p)}"').replace(' loading="lazy"', '')
html = re.sub(r'<img\b[^>]*>', img, html)

# ссылки на эту же страницу с якорем (логотип «питомник» → index.html#kennel) — внутри файла
html = re.sub(r'href="(?:\./)?' + re.escape(os.path.basename(page)) + r'#', 'href="#', html)
open(out, 'w', encoding='utf-8').write(html)
left = sorted(set(re.findall(r'(?:src|href)="((?:\.\./)*static/[^"]+)"', html)))
print(f'{out}: {os.path.getsize(out) / 1e6:.1f} МБ; не встроено: {left or "ничего"}')
