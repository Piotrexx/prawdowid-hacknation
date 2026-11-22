#!/usr/bin/env bash
# Test po wdrożeniu: strona, health API, Bielik, korpus.
#   bash scripts/smoke-test.sh
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; source .env; set +a
BASE="https://${DOMAIN:?brak DOMAIN w .env}"
fail=0
ok()  { echo "  OK   $*"; }
bad() { echo "  FAIL $*"; fail=1; }

echo "==> Kontenery"
docker compose -f docker-compose.prod.yml ps --format '{{.Service}}\t{{.Status}}'

echo "==> Frontend $BASE/"
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/" || true)
[[ "$code" == "200" ]] && ok "HTTP $code" || bad "HTTP $code"

echo "==> API $BASE/api/v1/health"
if health=$(curl -fsS --max-time 15 "$BASE/api/v1/health"); then
  echo "$health" | jq .
  [[ $(jq -r .status <<< "$health") == "ok" ]] && ok "status ok" || bad "status: $(jq -r .status <<< "$health")"
  [[ $(jq -r .bielik_configured <<< "$health") == "true" ]] && ok "Bielik skonfigurowany" || bad "Bielik nieskonfigurowany"
  docs=$(jq -r '.corpus_documents // 0' <<< "$health")
  (( docs > 0 )) && ok "korpus: $docs dokumentów" || bad "pusty korpus – uruchom: bash scripts/ingest.sh"
  mode=$(jq -r .retrieval_mode <<< "$health")
  [[ "$mode" == "hybrid" ]] && ok "retrieval: $mode" || bad "retrieval: $mode (oczekiwano hybrid)"
else
  bad "health nie odpowiada"
fi

echo "==> Model w Ollamie"
if docker compose -f docker-compose.prod.yml exec -T ollama ollama list | grep -qiF "${BIELIK_MODEL:-bielik}"; then
  ok "${BIELIK_MODEL:-bielik} pobrany"
else
  bad "brak modelu ${BIELIK_MODEL:-}"
fi

echo
(( fail == 0 )) && echo "Wszystko działa." || { echo "Są błędy – zobacz DEPLOY.md → Rozwiązywanie problemów."; exit 1; }
