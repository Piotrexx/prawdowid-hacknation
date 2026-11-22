#!/usr/bin/env bash
# Ingest źródeł do korpusu (w działającym kontenerze backendu).
#   bash scripts/ingest.sh               # wszystkie źródła
#   bash scripts/ingest.sh --only a,b    # wybrane źródła
#   bash scripts/ingest.sh --list        # lista źródeł
# Liczba dokumentów na źródło: INGEST_MAX (domyślnie 10).
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f docker-compose.prod.yml)
args=("$@")
if [[ ! " ${args[*]-} " =~ " --max " && ! " ${args[*]-} " =~ " --list " ]]; then
  args+=(--max "${INGEST_MAX:-10}")
fi

echo "[$(date -Is)] ingest start ${args[*]}"
"${COMPOSE[@]}" exec -T backend .venv/bin/python -m app.ingest.run "${args[@]}"
echo "[$(date -Is)] ingest koniec"
