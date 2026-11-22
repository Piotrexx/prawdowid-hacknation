#!/usr/bin/env bash
# Odtworzenie bazy z kopii (NADPISUJE bieżącą bazę):
#   bash scripts/restore.sh backups/prawdowid-2026-11-22-0400.sql.gz
set -euo pipefail
cd "$(dirname "$0")/.."

file="${1:?podaj plik kopii, np. backups/prawdowid-....sql.gz}"
[[ -f "$file" ]] || { echo "Brak pliku: $file" >&2; exit 1; }

set -a; source .env; set +a
DB="${POSTGRES_DB:-prawdowid}"
USER_="${POSTGRES_USER:-prawdowid}"
COMPOSE=(docker compose -f docker-compose.prod.yml)

read -r -p "Nadpisać bazę '$DB' kopią $file? Wpisz TAK: " answer
[[ "$answer" == "TAK" ]] || { echo "Przerwano."; exit 1; }

echo "==> Zatrzymuję backend i bota"
"${COMPOSE[@]}" --profile bot stop backend discord-bot

echo "==> Odtwarzam"
gunzip -c "$file" | "${COMPOSE[@]}" exec -T postgres \
  psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 --quiet > /dev/null

echo "==> Uruchamiam backend"
"${COMPOSE[@]}" start backend
echo "Gotowe. Bota (jeśli używasz) uruchom: ${COMPOSE[*]} --profile bot up -d discord-bot"
