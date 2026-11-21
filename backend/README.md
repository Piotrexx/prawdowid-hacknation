# Prawdowid – backend (FastAPI)

Wykrywanie fake news: **URL → trafilatura → Bielik 4.5B Instruct (keywords) → Google Fact Check Tools → DeepSeek (verdict)**

## Uruchomienie (Docker - zalecane)

```bash
cp backend/.env.example backend/.env     # Wypełnij klucze API
docker compose up --build
```

- Backend API: <http://localhost:8000>
- Dokumentacja OpenAPI: <http://localhost:8000/docs>
- Frontend: <http://localhost:3000>
- Ollama (Bielik): <http://localhost:11434>

## Uruchomienie lokalne (bez Docker)

```bash
cd backend
cp .env.example .env     # Wypełnij: LLM_API_KEY (DeepSeek), GOOGLE_FACTCHECK_API_KEY, ADMIN_TOKEN, ID_HASH_SALT
# Uruchom Ollama z modelem Bielik:
ollama pull bielik:4.5b-instruct
ollama serve
# W drugim terminalu:
uv sync
uv run uvicorn app.main:app --port 8000
```

## Konfiguracja

Wszystkie ustawienia to zmienne środowiskowe – pełna lista w [.env.example](.env.example) i [app/config.py](app/config.py).

| Zmienna | Znaczenie |
|---|---|
| `LLM_PROVIDER`, `LLM_MODEL` | `openai_compatible` (domyślnie `deepseek-flash` - DeepSeek V4.1 Flash; także Mistral, Ollama, vLLM) |
| `LLM_BASE_URL`, `LLM_API_KEY` | Dostęp do modelu DeepSeek |
| `BIELIK_BASE_URL`, `BIELIK_MODEL` | Ollama/vLLM endpoint dla Bielik 4.5B (domyślnie `http://localhost:11434`, `bielik:4.5b-instruct`) |
| `GOOGLE_FACTCHECK_API_KEY` | Klucz Google Fact Check Tools API (https://developers.google.com/fact-check/tools/api) |
| `ADMIN_TOKEN` | Token panelu admina (bez niego panel wyłączony) |
| `ID_HASH_SALT` | Sól do skracania identyfikatorów (adresy IP w limicie żądań) |
| `RATE_LIMIT_PER_MINUTE` | Limit żądań na IP |
| `RETENTION_DAYS` | Retencja danych |

## API (`/api/v1`)

| Metoda | Ścieżka | Opis |
|---|---|---|
| POST | `/checks` | Sprawdzenie URL artykułu (`{url, session_id?}`) |
| GET | `/checks/{id}` | Zapisany wynik |
| DELETE | `/sessions/{session_id}` | Usunięcie danych sesji |
| GET | `/health` | Stan usługi, modele, miejsce przetwarzania |
| GET | `/admin/metrics`, `/admin/checks`, `/admin/export` | Panel admina (`X-Admin-Token`) |

### Przykład żądania:

```bash
curl -s localhost:8000/api/v1/checks -H 'Content-Type: application/json' \
  -d '{"url": "https://example.org/artykul-do-sprawdzenia"}'
```

### Przykład odpowiedzi:

```json
{
  "id": "abc123...",
  "created_at": "2024-11-21T10:00:00Z",
  "channel": "web",
  "status": "completed",
  "input": {
    "kind": "url",
    "text": "Treść artykułu...",
    "url": "https://example.org/artykul-do-sprawdzenia",
    "title": "Tytuł artykułu"
  },
  "verdict": "fake_news",
  "verdict_label": "fake_news",
  "confidence": 0.92,
  "justification": "Artykuł zawiera fałszywe informacje...",
  "keywords": ["fake news", "dezinformacja", "weryfikacja", ...],
  "main_topic": "Artykuł szerzy dezinformację na temat...",
  "fact_check_results": [
    {
      "claim": "Twierdzenie do sprawdzenia",
      "claimant": "Jan Kowalski",
      "claim_date": "2024-01-15",
      "claim_review_url": "https://demagog.org.pl/sprawdzenie/123",
      "claim_review_title": "Sprawdzenie: Twierdzenie jest fałszywe",
      "publisher_name": "Demagog",
      "publisher_site": "demagog.org.pl",
      "rating": "Fałsz",
      "textual_rating": "Fałsz",
      "url": "https://demagog.org.pl/sprawdzenie/123"
    }
  ],
  "limitations": [
    "Analiza opiera się na treści artykułu pobranej w momencie sprawdzenia...",
    "Werdykt to interpretacja modelu językowego..."
  ],
  "meta": {
    "duration_ms": 3500,
    "stages_ms": {"fetch": 800, "keywords": 1200, "factcheck": 500, "verdict": 1000},
    "provider": "openai_compatible",
    "model": "deepseek-flash",
    "bielik_model": "bielik:4.5b-instruct",
    "llm_calls": 2,
    "tokens_in": 1500,
    "tokens_out": 300,
    "cost_usd": 0.0012,
    "processing_location": "...",
    "cached": false
  }
}
```

## Pipeline - jak to działa

1. **Pobranie artykułu (trafilatura)** - Użytkownik podaje URL, system pobiera stronę i ekstrahuje czysty tekst (tytuł + treść) używając `trafilatura`.

2. **Ekstrakcja słów kluczowych (Bielik 4.5B Instruct)** - Model Bielik analizuje tytuł i treść, wyciąga do 10 najważniejszych słów kluczowych/fraz do wyszukiwania fact-checków. Prompt **wyłącznie po polsku**.

3. **Google Fact Check Tools API** - Słowa kluczowe wysyłane do Google Fact Check API, pobierane **top 5** najbardziej pasujących sprawdzeń faktów.

4. **Werdykt (DeepSeek)** - DeepSeek analizuje: treść artykułu, słowa kluczowe, znalezione fact-checki i wydaje ostateczny werdykt:
   - `fake_news` - fałszywe informacje (dezinformacja)
   - `prawdziwe` - informacje potwierdzone przez źródła
   - `niepewne` - brak wystarczających dowodów
   - `satyna` - artykuł satyryczny
   - `opinia` - wyrażenie opinii, nie faktów

## Testy i ewaluacja

```bash
cd backend
uv run pytest                       # testy jednostkowe i integracyjne (z mockami)
uv run ruff check .
uv run python -m eval.run_eval      # ewaluacja na prawdziwym modelu (kosztuje)
```

## Struktura projektu

```
backend/
├── app/
│   ├── api/              # Endpointy FastAPI
│   │   ├── checks.py     # POST /checks, GET /health
│   │   ├── admin.py      # Panel admina
│   │   └── deps.py       # Rate limiting, auth
│   ├── core/
│   │   ├── pipeline.py   # GŁÓWNY PIPELINE: fetch → keywords → factcheck → verdict
│   │   └── prompts.py    # Prompty dla Bielik i DeepSeek (TYLKO PO POLSKU)
│   ├── llm/              # Providerzy LLM (DeepSeek, Bielik via OpenAI-compat)
│   ├── security/         # URL fetch (trafilatura), rate limiting
│   ├── schemas.py        # Modele Pydantic (API contract)
│   ├── config.py         # Konfiguracja (pydantic-settings)
│   ├── store/            # SQLite storage
│   ├── textutil.py       # Utility functions
│   └── main.py           # FastAPI app factory
├── tests/                # Testy (conftest, test_units, test_pipeline)
├── eval/                 # Ewaluacja na prawdziwym modelu
├── data/                 # Baza danych SQLite
├── pyproject.toml        # Zależności
├── Dockerfile
├── .env.example
└── README.md
```

## Wymagane klucze API

1. **DeepSeek API** - https://platform.deepseek.com/ (dla werdyktu)
2. **Google Fact Check Tools API** - https://developers.google.com/fact-check/tools/api (dla fact-checków)
3. **Ollama + Bielik 4.5B** - `ollama pull bielik:4.5b-instruct` (dla słów kluczowych)

## Uwagi

- Backend działa **tylko z URL** (nie ma już endpointu dla czystego tekstu ani obrazów)
- Wszystkie prompty są **wyłącznie po polsku**
- System zapisuje wyniki do SQLite (`data/prawdowid.db`)
- Limity zapytań: domyślnie 10/min na IP