#!/usr/bin/env bash
# Резервная копия старого сайта (OpenCart) на виртуальном хостинге SpaceWeb — ПЕРЕД переездом.
# Запускать на хостинге по SSH:  bash backup-old-site.sh   → в домашней папке появится bro-old-<дата>.tgz и .sql
# Потом скачать к себе:  scp ЛОГИН@77.222.40.7:'bro-old-*' ~/site11/backup-old/
set -euo pipefail
cd ~
ROOT=$(dirname "$(find ~ -maxdepth 4 -name config.php -path '*admin*' 2>/dev/null | head -1)")/..
ROOT=$(cd "$ROOT" && pwd)
echo "Папка сайта: $ROOT"
CFG="$ROOT/config.php"
get() { php -r "include '$CFG'; echo $1;"; }
DB_HOST=$(get DB_HOSTNAME); DB_USER=$(get DB_USERNAME); DB_PASS=$(get DB_PASSWORD); DB_NAME=$(get DB_DATABASE)
STAMP=$(date +%F)
mysqldump -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" --single-transaction --default-character-set=utf8mb4 "$DB_NAME" > "bro-old-$STAMP.sql"
tar -czf "bro-old-$STAMP.tgz" -C "$(dirname "$ROOT")" "$(basename "$ROOT")"
ls -lh "bro-old-$STAMP".*
