#!/usr/bin/env bash
# Kopia bazy do backups/prawdowid-RRRR-MM-DD-GGMM.sql.gz, starsze niż KEEP_DAYS (domyślnie 14) są usuwane.
# Cron: 30 3 * * * cd /opt/prawdowid && bash scripts/backup.sh >> /var/log/prawdowid-backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; source .env; set +a
DB="${POSTGRES_DB:-prawdowid}"
USER_="${POSTGRES_USER:-prawdowid}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p backups
chmod 700 backups
out="backups/prawdowid-$(date +%Y-%m-%d-%H%M).sql.gz"

docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$USER_" -d "$DB" --clean --if-exists --no-owner \
  | gzip -9 > "$out.tmp"
mv "$out.tmp" "$out"
chmod 600 "$out"

find backups -name 'prawdowid-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
echo "[$(date -Is)] kopia: $out ($(du -h "$out" | cut -f1))"
