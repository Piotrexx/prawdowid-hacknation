# Prawdowid – backend (FastAPI)

## Uruchomienie

```bash
cp .env.example .env     # LLM_API_KEY (klucz DeepSeek), ADMIN_TOKEN, ID_HASH_SALT
uv sync
uv run uvicorn app.main:app --port 8000
```

- Dokumentacja OpenAPI: <http://localhost:8000/docs>, schemat: `/openapi.json`.
- Pierwszy start pobiera model embeddingów (ok. 220 MB) i liczy indeks; wynik trafia do `data/index/`.
- Bez klucza API usługa działa w trybie awaryjnym: każde sprawdzenie zwraca jawny błąd techniczny.

## Konfiguracja

Wszystkie ustawienia to zmienne środowiskowe – pełna lista z opisami w [.env.example](.env.example)
i [app/config.py](app/config.py). Najważniejsze:

| Zmienna | Znaczenie |
|---|---|
| `LLM_PROVIDER`, `LLM_MODEL` | `openai_compatible` (domyślnie `deepseek-flash`, czyli DeepSeek V4.1 Flash; także Mistral, Ollama, vLLM), `anthropic`, `none` |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_JSON_MODE` / `ANTHROPIC_API_KEY` | dostęp do modelu |
| `ADMIN_TOKEN` | token panelu moderatora (bez niego panel jest wyłączony) |
| `ID_HASH_SALT` | sól do skracania identyfikatorów (adresy IP w limicie żądań) |
| `EMBEDDINGS` | `fastembed` (lokalny model) lub `off` |
| `RETENTION_DAYS`, `RATE_LIMIT_PER_MINUTE` | retencja i limit żądań |
| `MODERATOR_WEBHOOK_URL` | powiadomienia o sprawach (Slack / Discord) |

## API (`/api/v1`)

| Metoda | Ścieżka | Opis |
|---|---|---|
| POST | `/checks` | sprawdzenie tekstu lub URL (`{text?, url?, session_id?}`) |
| POST | `/checks/image` | sprawdzenie zrzutu ekranu (multipart `file`) |
| GET | `/checks/{id}` | zapisany wynik |
| DELETE | `/sessions/{session_id}` | usunięcie danych sesji |
| GET | `/sources` | katalog źródeł, statystyki korpusu, zasady |
| GET | `/health` | stan usługi, model, miejsce przetwarzania |
| GET | `/admin/metrics`, `/admin/cases`, `/admin/events`, `/admin/checks` | panel moderatora (`X-Admin-Token`) |
| PATCH | `/admin/cases/{id}` | zmiana statusu / notatki sprawy |
| GET | `/admin/export?format=csv\|json` | eksport przebiegu sprawdzeń |

Przykład:

```bash
curl -s localhost:8000/api/v1/checks -H 'Content-Type: application/json' \
  -d '{"text": "Polska została wybrana do Wspólnej Jednostki Kontrolnej ONZ."}'
```

## Korpus, testy, ewaluacja

```bash
uv run python -m app.ingest.run     # aktualizacja korpusu wg data/sources.yaml
uv run pytest                       # testy (model podstawiony)
uv run ruff check .
uv run python -m eval.run_eval      # mierniki na prawdziwym modelu (kosztuje)
```

## Dodawanie elementów

- **Kanał:** nowy router, który zamienia wiadomość na `Submission` (`Submission.from_message`), woła
  `service.check()` i przedstawia `CheckResponse` w formie właściwej dla kanału; dołącz go w `app/main.py`.
- **Dostawca modelu:** klasa z metodą `structured()` zgodną z `app/llm/base.py::LLMProvider`, wpis w `app/llm/factory.py`.
- **Źródło:** wpis w `data/sources.yaml` (z uzasadnieniem i licencją); nowy typ źródła = funkcja w `app/ingest/connectors.py`.
