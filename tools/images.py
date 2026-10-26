#!/usr/bin/env python3
"""Готовит фото для сайта: из static/img/products/<slug>.jpg (или любого фото) делает
800×600 JPG + WebP 400/800 px. Нужен Pillow:  pip install pillow

    python3 tools/images.py                     # пересчитать все WebP
    python3 tools/images.py новое_фото.jpg slug # добавить/заменить фото товара
"""
import os, sys
from PIL import Image, ImageOps, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD = os.path.join(ROOT, 'static/img/products')
BRAND = os.path.join(ROOT, 'static/img/brand')

def trim(im, tol=18):
    for bg in ((255, 255, 255), (0, 0, 0)):
        diff = ImageChops.difference(im, Image.new('RGB', im.size, bg)).convert('L').point(lambda v: 255 if v > tol else 0)
        box = diff.getbbox()
        if box and (box[2] - box[0]) * (box[3] - box[1]) < im.size[0] * im.size[1] * 0.97:
            im = im.crop(box)
    return im

def fit(im, w, h):
    im = trim(ImageOps.exif_transpose(im).convert('RGB'))
    W, H = im.size; r = w / h
    if W / H > r:
        nw = int(H * r); im = im.crop(((W - nw) // 2, 0, (W - nw) // 2 + nw, H))
    else:
        nh = int(W / r); top = max(0, int((H - nh) * 0.45)); im = im.crop((0, top, W, top + nh))
    return im.resize((w, h), Image.LANCZOS)

def variants(src, out_dir, stem, sizes):
    im = Image.open(src).convert('RGB')
    for w in sizes:
        d = os.path.join(out_dir, f'w{w}'); os.makedirs(d, exist_ok=True)
        h = round(im.size[1] * w / im.size[0])
        im.resize((w, h), Image.LANCZOS).save(os.path.join(d, stem + '.webp'), 'WEBP', quality=78, method=6)

def main():
    if len(sys.argv) == 3:
        src, slug = sys.argv[1:]
        fit(Image.open(src), 800, 600).save(os.path.join(PROD, slug + '.jpg'), 'JPEG', quality=80, optimize=True, progressive=True)
        print(f'фото {slug}.jpg готово — пропишите "img": "{slug}.jpg" в data/products.json')
    for f in sorted(os.listdir(PROD)):
        if f.endswith('.jpg'):
            variants(os.path.join(PROD, f), PROD, f[:-4], (400, 800))
    variants(os.path.join(BRAND, 'hero.jpg'), BRAND, 'hero', (600, 1100))
    print('WebP готовы')

if __name__ == '__main__':
    main()
