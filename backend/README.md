# Prawdowid – backend (FastAPI)

Weryfikacja informacji oparta na **jawnym katalogu źródeł**: twierdzenia są oceniane na podstawie
cytatów sprawdzonych w korpusie (575 dokumentów, 11 domen, 4 typy źródeł), a słowa kluczowe,
Google Fact Check Tools i podsumowanie modelu stanowią warstwę wspierającą.

**tekst / URL / obraz → maskowanie PII → wydzielenie twierdzeń → wyszukiwanie w korpusie
(BM25 + embeddingi) → ocena dowodów → reguły werdyktu → kolejka moderatora**

## Uruchomienie (Docker - zalecane)

```bash
cp backend/.env.example backend/.env     # Wypełnij klucze API
docker compose up --build
```

- Backend API: <http://localhost:8000>
- Dokumentacja OpenAPI: <http://localhost:8000/docs>
- Frontend: <http://localhost:3000>
- Ollama (Bielik, słowa kluczowe): <http://localhost:11434>

## Uruchomienie lokalne (bez Docker)

```bash
cd backend
cp .env.example .env     # Wypełnij: LLM_API_KEY (DeepSeek), GOOGLE_FACTCHECK_API_KEY, ADMIN_TOKEN, ID_HASH_SALT
# Uruchom Ollama z modelem Bielik (słowa kluczowe):
ollama pull SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
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
| `BIELIK_BASE_URL`, `BIELIK_MODEL` | Ollama/vLLM z Bielikiem dla słów kluczowych (domyślnie `http://localhost:11434/v1`, `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0`). Puste `BIELIK_BASE_URL` wyłącza etap. |
| `GOOGLE_FACTCHECK_API_KEY` | Klucz Google Fact Check Tools API (https://developers.google.com/fact-check/tools/api) |
| `ADMIN_TOKEN` | Token panelu admina (bez niego panel wyłączony) |
| `ID_HASH_SALT` | Sól do skracania identyfikatorów (adresy IP w limicie żądań) |
| `RATE_LIMIT_PER_MINUTE` | Limit żądań na IP |
| `RETENTION_DAYS` | Retencja danych |

## API (`/api/v1`)

| Metoda | Ścieżka | Opis |
|---|---|---|
| POST | `/checks` | Sprawdzenie tekstu lub URL (`{text?, url?, session_id?}`) |
| POST | `/checks/image` | Sprawdzenie obrazu (multipart: `file`, `session_id?`) |
| GET | `/checks/{id}` | Zapisany wynik |
| GET | `/sources` | Katalog źródeł, statystyki korpusu, zasady kwalifikacji |
| POST | `/consent` | Zapis zgody na politykę prywatności (`{policy_version, session_id?, accepted?}`) |
| GET | `/consent/{session_id}` | Czy sesja zaakceptowała daną wersję polityki |
| DELETE | `/sessions/{session_id}` | Usunięcie danych sesji (wraz ze zgodą) |
| GET | `/health` | Stan usługi, modele, tryb wyszukiwania, statystyki korpusu |
| GET | `/admin/metrics`, `/admin/checks`, `/admin/cases`, `/admin/events`, `/admin/export` | Panel moderatora (`X-Admin-Token`) |
| PATCH | `/admin/cases/{id}` | Zmiana stanu sprawy moderatora |

`session_id` można podać w treści żądania albo zostawić w ciasteczku `prawdowid_session` –
backend bierze je z ciasteczka, gdy brakuje go w treści.

### Przykład żądania:

```bash
curl -s localhost:8000/api/v1/checks -H 'Content-Type: application/json' \
  -d '{"text": "Polska została wybrana do Wspólnej Jednostki Kontrolnej ONZ."}'
```

### Przykład odpowiedzi:

Rozstrzygające są `claims[]` – każde twierdzenie z własnym werdyktem i **dosłownymi cytatami**
sprawdzonymi w źródle. Pola `verdict`, `keywords` i `fact_check_results` to warstwa wspierająca.

```json
{
  "id": "abc123...",
  "created_at": "2026-11-21T10:00:00Z",
  "channel": "web",
  "status": "completed",
  "input": { "kind": "text", "text": "Polska została wybrana..." },
  "summary": "Liczba sprawdzonych twierdzeń: 1. Wyniki: potwierdzone – 1.",
  "claims": [
    {
      "id": "c1",
      "text": "Polska została wybrana do Wspólnej Jednostki Kontrolnej ONZ.",
      "verdict": "potwierdzone",
      "verdict_label": "Potwierdzone",
      "justification": "Źródło urzędowe potwierdza wybór [E1].",
      "strength": {
        "level": "mocna",
        "score": 0.8,
        "factors": [
          { "code": "source_quality", "label": "Jakość źródła",
            "value": "źródło pierwotne lub urzędowe", "effect": "plus" }
        ]
      },
      "evidence": [
        {
          "id": "E1",
          "stance": "supports",
          "quote": "Polska została wybrana do Wspólnej Jednostki Kontrolnej Organizacji Narodów Zjednoczonych...",
          "source": {
            "doc_id": "msz-jiu-2026",
            "title": "Polska dołącza do Wspólnej Jednostki Kontrolnej ONZ",
            "publisher": "Ministerstwo Spraw Zagranicznych RP",
            "url": "https://www.gov.pl/web/dyplomacja/polska-dolacza-do-wspolnej-jednostki-kontrolnej-onz",
            "source_type": "official",
            "source_name": "gov.pl – komunikaty",
            "published_at": "2026-11-10"
          },
          "archival": false
        }
      ],
      "conflict": false,
      "missing": null,
      "risk": "standard"
    }
  ],
  "warnings": [],
  "incident_matches": [],
  "moderator_case": { "state": "none" },

  "verdict": "potwierdzone",
  "verdict_label": "Potwierdzone",
  "confidence": 0.9,
  "justification": "Podsumowanie spójne z oceną twierdzenia...",
  "keywords": ["Polska", "Wspólna Jednostka Kontrolna ONZ", "ONZ"],
  "main_topic": "Wybór Polski do Wspólnej Jednostki Kontrolnej ONZ",
  "fact_check_results": [
    {
      "claim": "Twierdzenie sprawdzone przez redakcję",
      "claim_review_url": "https://demagog.org.pl/sprawdzenie/123",
      "claim_review_title": "Sprawdzenie: twierdzenie jest fałszywe",
      "publisher_name": "Demagog",
      "publisher_site": "demagog.org.pl",
      "rating": "Fałsz"
    }
  ],
  "limitations": [
    "Odpowiedź opiera się wyłącznie na źródłach z katalogu Prawdowida...",
    "Uzasadnienie to interpretacja modelu językowego..."
  ],
  "meta": {
    "duration_ms": 48000,
    "stages_ms": { "input": 0, "extract": 1154, "keywords": 44101,
                   "factcheck": 532, "verify": 44634, "summary": 3094 },
    "provider": "openai_compatible",
    "model": "deepseek-flash",
    "bielik_model": "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0",
    "llm_calls": 4,
    "tokens_in": 1500,
    "tokens_out": 300,
    "bielik_tokens_in": 615,
    "bielik_tokens_out": 127,
    "cost_usd": 0.0012,
    "retrieval_mode": "hybrid",
    "corpus_version": "10d51f43c4ec",
    "processing_location": "...",
    "cached": false
  }
}
```

## Pipeline - jak to działa

Pełny opis: [`docs/ARCHITEKTURA.md`](../docs/ARCHITEKTURA.md).

### Warstwa dowodowa (rozstrzygająca)

1. **Przygotowanie wejścia** - tekst, URL (pobranie przez `trafilatura`, ochrona SSRF i robots.txt)
   albo obraz (odczyt tekstu modelem, usunięcie EXIF). Maskowanie danych osobowych
   (`security/pii.py`) i wykrycie prób prompt injection (`security/injection.py`).

2. **Wydzielenie twierdzeń (model)** - do `MAX_CLAIMS` twierdzeń z rodzajem
   (fakt / opinia / prognoza), zapytaniami do wyszukiwarki i poziomem ryzyka.

3. **Wyszukiwanie w korpusie** - BM25 + embeddingi, fuzja RRF, preferencja nowszych źródeł
   (`retrieval/index.py`). Bez modelu embeddingów działa samo BM25.

4. **Ocena dowodów (model)** - dla każdego fragmentu stanowisko
   (`supports` / `refutes` / `context` / `irrelevant`) i **dosłowny cytat**.

5. **Reguły werdyktu (kod)** - `core/verdict.py` sprawdza, czy każdy cytat naprawdę występuje
   w źródle; niepotwierdzone są odrzucane. Werdykt wynika z potwierdzonych cytatów, nie z etykiety
   modelu: `potwierdzone`, `falszywe`, `wprowadzajace_w_blad`,
   `brak_wystarczajacych_dowodow`, `nie_podlega_weryfikacji`. Liczona jest też siła podstawy.

6. **Pętla informacji** - nierozstrzygnięte twierdzenia trafiają do kolejki moderatora,
   podobne zgłoszenia są grupowane w jedną sprawę (`core/cases.py`).

### Warstwa wspierająca (równolegle, nigdy rozstrzygająca)

- **Słowa kluczowe (Bielik, lokalnie)** - Bielik 4.5B v3.0 Instruct przez Ollamę/vLLM wyciąga
  do 10 słów kluczowych i główny temat. Prompt **wyłącznie po polsku**.
  Przy awarii: model zdalny, a potem zapytania z kroku 2.
- **Google Fact Check Tools** - top 5 sprawdzeń dopasowanych do słów kluczowych.
- **Podsumowanie całości (model)** - jeden werdykt dla całego materiału w polu `verdict`.
  `_reconcile()` pilnuje, by nie było mocniejsze niż dowody.

Awaria którejkolwiek części warstwy wspierającej zostawia oceny twierdzeń nietknięte
i daje tylko ostrzeżenie.

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
│   │   ├── pipeline.py   # GŁÓWNY PIPELINE (jedna ścieżka dla wszystkich kanałów)
│   │   ├── verdict.py    # REGUŁY WERDYKTU: weryfikacja cytatów, siła podstawy
│   │   ├── cases.py      # Pętla informacji: kolejka moderatora, grupowanie spraw
│   │   ├── media.py      # Obraz: walidacja, metadane, usunięcie EXIF
│   │   └── prompts.py    # Prompty i schematy odpowiedzi (TYLKO PO POLSKU)
│   ├── retrieval/
│   │   ├── index.py      # Korpus w pamięci: BM25 + embeddingi, RRF
│   │   └── context.py    # Znane incydenty i status źródła (kontekst, nie dowód)
│   ├── ingest/           # 11 konektorów do źródeł + budowa korpusu
│   ├── llm/              # Providerzy LLM (OpenAI-compat, Anthropic)
│   ├── security/         # URL fetch, rate limiting, maskowanie PII, prompt injection
│   ├── catalog.py        # Katalog źródeł i rekord korpusu
│   ├── schemas.py        # Modele Pydantic (API contract)
│   ├── config.py         # Konfiguracja (pydantic-settings)
│   ├── store/            # SQLite/Postgres: sprawdzenia, sprawy, zgody, zdarzenia
│   ├── textutil.py       # Tokenizacja, normalizacja cytatów, podobieństwo
│   └── main.py           # FastAPI app factory
├── tests/                # Testy (conftest, test_units, test_pipeline, test_llm_providers)
├── eval/                 # Ewaluacja na prawdziwym korpusie i modelu
├── data/
│   ├── sources.yaml      # Katalog źródeł (12 wpisów) i zasady kwalifikacji
│   ├── source_status.yaml# Uwagi o statusie źródeł
│   └── corpus/           # documents.jsonl (575 dokumentów) + manifest.json
├── pyproject.toml        # Zależności
├── Dockerfile
├── .env.example
└── README.md
```

## Wymagane klucze API

1. **DeepSeek API** - https://platform.deepseek.com/ (dla werdyktu)
2. **Google Fact Check Tools API** - https://developers.google.com/fact-check/tools/api (dla fact-checków)
3. **Ollama + Bielik 4.5B v3.0 Instruct** - `ollama pull SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0` (dla słów kluczowych; opcjonalne – bez niego używany jest model zdalny). Bielik nie ma tagu `latest`, więc kwantyzację podaje się wprost.

## Uwagi

- Backend działa **tylko z URL** (nie ma już endpointu dla czystego tekstu ani obrazów)
- Wszystkie prompty są **wyłącznie po polsku**
- System zapisuje wyniki do SQLite (`data/prawdowid.db`)
- Limity zapytań: domyślnie 10/min na IP