#!/usr/bin/env bash
# Откатить КОД сайта на одну из прошлых версий. Данные из админки (товары, фото, объявления, заказы) не трогаются.
#   cd /home/bro/site
#   sudo -u bro bash deploy/rollback.sh          # показать последние версии
#   sudo -u bro bash deploy/rollback.sh 4eff19b  # вернуть код этой версии
# Вернуться на самую свежую версию: sudo -u bro bash deploy/update.sh
set -euo pipefail
cd "$(dirname "$0")/.."
git fetch -q origin
if [ $# -eq 0 ]; then
  echo "Последние версии (самая новая сверху):"
  git log --date=format:'%d.%m %H:%M' --format='  %h  %ad  %s' -15 origin/main
  echo; echo "Откат: sudo -u bro bash deploy/rollback.sh <код слева>"
  exit 0
fi
REV=$1
git cat-file -e "$REV^{commit}" 2>/dev/null || { echo "Нет такой версии: $REV"; exit 1; }
# deploy/ не откатываем — скрипты обновления и отката остаются свежими
git checkout "$REV" -- build.py admin tools Dockerfile .dockerignore compose.yaml \
  static/css static/js static/fonts static/img/brand
docker compose -f deploy/compose.prod.yaml up -d --build
docker image prune -f >/dev/null; docker builder prune -f >/dev/null
echo "Код откатан на $(git log -1 --format='%h «%s»' "$REV"). Данные из админки не тронуты."
