#!/usr/bin/env bash
# Первичная настройка чистого VPS (Ubuntu 24.04) под сайт БРО. Запускать от root на сервере:
#   bash setup-vps.sh
# Делает: Docker из репозитория Ubuntu, файрвол (22/80/443), пользователь bro, код сайта в /home/bro/site,
# пароль админки и настройки почты (вводятся вручную, в чат их не присылать), запуск, ежедневный бэкап.
set -euo pipefail
REPO=${REPO:-https://github.com/AISUPh2k/bro-butcher-site.git}
DIR=/home/bro/site

echo "== пакеты"
apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 git ufw

echo "== файрвол"
ufw allow OpenSSH; ufw allow 80/tcp; ufw allow 443/tcp; ufw allow 443/udp
ufw --force enable

echo "== пользователь bro (uid 1000 — как в контейнере)"
id bro >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash bro
usermod -aG docker bro

echo "== код сайта"
if [ ! -d "$DIR/.git" ]; then sudo -u bro git clone -q "$REPO" "$DIR"; fi  # обновления — только deploy/update.sh
cd "$DIR"
sudo -u bro mkdir -p orders data/backups

echo "== пароль админки"
if [ ! -f admin.secret.json ]; then sudo -u bro python3 tools/admin_server.py --password; fi

echo "== почта для заказов"
if [ ! -f orders.config.json ]; then
  read -rp "Ящик-отправитель (например, zakaz@yandex.ru): " FROM
  read -rp "SMTP-сервер [smtp.yandex.ru]: " HOST; HOST=${HOST:-smtp.yandex.ru}
  read -rsp "Пароль ПРИЛОЖЕНИЯ этого ящика (не основной): " PASS; echo
  read -rp "Куда слать заказы (через запятую): " TO
  sudo -u bro python3 - "$FROM" "$HOST" "$PASS" "$TO" <<'PY'
import json, os, sys
f, h, p, t = sys.argv[1:5]
json.dump({'mode': 'smtp', 'smtp_host': h, 'smtp_port': 465, 'security': 'ssl', 'user': f, 'password': p, 'from': f,
           'to': [x.strip() for x in t.split(',') if x.strip()]}, open('orders.config.json', 'w'), ensure_ascii=False, indent=1)
os.chmod('orders.config.json', 0o600)
PY
fi

echo "== запуск"
sudo -u bro docker compose -f deploy/compose.prod.yaml up -d --build

echo "== ежедневный бэкап данных и заказов (03:30, хранится 30 дней)"
cat > /etc/cron.d/bro-backup <<CRON
30 3 * * * bro tar -czf /home/bro/backup-\$(date +\%F).tgz -C $DIR data orders static/img/products admin.secret.json orders.config.json && find /home/bro -name 'backup-*.tgz' -mtime +30 -delete
CRON

echo "Готово. Проверка: curl -sI http://127.0.0.1 (после смены DNS — https://myaso-sobakam-bro.ru)"
