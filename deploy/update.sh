#!/usr/bin/env bash
# Обновить КОД сайта на VPS, не трогая то, что Наталья меняет в админке
# (data/*.json, фото товаров, заказы, пароль, почта). Запускать под пользователем bro:
#   cd ~/site && bash deploy/update.sh
set -euo pipefail
cd "$(dirname "$0")/.."
git fetch -q origin
git checkout origin/main -- build.py admin tools Dockerfile .dockerignore compose.yaml deploy \
  static/css static/js static/fonts static/img/brand
docker compose -f deploy/compose.prod.yaml up -d --build
echo "Код обновлён. Данные из админки не тронуты."
