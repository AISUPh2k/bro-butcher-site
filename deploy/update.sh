#!/usr/bin/env bash
# Обновить КОД сайта на VPS, не трогая то, что Наталья меняет в админке
# (data/*.json, фото товаров, заказы, пароль, почта). Запускать под пользователем bro:
#   cd ~/site && bash deploy/update.sh
set -euo pipefail
cd "$(dirname "$0")/.."
git fetch -q origin
git checkout origin/main -- build.py admin tools Dockerfile .dockerignore compose.yaml deploy \
  static/css static/js static/fonts static/img/brand static/img/kennel
# новые настройки из новой версии — в серверный site.json (правки из админки остаются)
git show origin/main:data/site.json > /tmp/bro-site-new.json && python3 deploy/migrate_data.py /tmp/bro-site-new.json
docker compose -f deploy/compose.prod.yaml up -d --build
docker image prune -f >/dev/null; docker builder prune -f >/dev/null
echo "Код обновлён. Данные из админки не тронуты."
