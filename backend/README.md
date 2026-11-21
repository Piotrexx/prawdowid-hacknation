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
| `IMAGE_SEARCH_ENGINES` | Silniki odwrotnego wyszukiwania obrazu (domyślnie `yandex,tineye`; dostępny też `bing`) |
| `IMAGE_SEARCH_TIMEOUT_S`, `IMAGE_CACHE_HOURS` | Limit czasu na silnik; jak długo wynik dla tych samych bajtów zdjęcia jest brany z bazy |

## API (`/api/v1`)

| Metoda | Ścieżka | Opis |
|---|---|---|
| POST | `/checks` | Sprawdzenie URL artykułu (`{url, session_id?}`) |
| POST | `/checks/image` | Sprawdzenie, czy zdjęcie nie zostało zmienione (multipart: `file`, `session_id?`) |
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

## Weryfikacja zdjęć – jak to działa

`POST /checks/image` nie używa modelu językowego ani płatnych API:

1. **Przygotowanie** – walidacja (JPEG/PNG/WebP/GIF, max 10 MB, max 40 Mpx), odczyt EXIF (bez GPS), kopia JPEG **bez metadanych** do wysłania dalej.
2. **Odwrotne wyszukiwanie** ([PicImageSearch](https://github.com/kitUIN/PicImageSearch), scraping) – Yandex i TinEye równolegle. Awaria jednego silnika daje ostrzeżenie, awaria wszystkich – błąd (nie werdykt).
3. **Pobranie kopii** – do 10 kopii, pełny obraz ze strony źródłowej (z ochroną SSRF jak przy artykułach), w razie błędu miniatura z wyszukiwarki.
4. **Porównanie** ([app/core/image_compare.py](app/core/image_compare.py)) – dopasowanie kopii do zdjęcia (SIFT + RANSAC, obsługuje kadrowanie i skalowanie), dopasowanie jasności/kontrastu z pominięciem odstających pikseli, różnica w siatce 8×8. Globalny hash (pHash) **nie wystarcza** – doklejony obiekt zmienia go o 1–2 bity.
5. **Ocena** – zdjęcie jest podejrzane, gdy **w tym samym miejscu** różni się od większości (≥60%, min. 2) kopii. Różnice tylko w pojedynczych kopiach (podpisy, znaki wodne) nie są brane pod uwagę.

| `image_analysis.assessment` | Werdykt | Znaczenie |
|---|---|---|
| `manipulation_suspected` | `fake_news` | Fragment różni się od większości kopii; `changed_regions` wskazuje gdzie (współrzędne 0–1) |
| `consistent_with_copies` | `prawdziwe` | Co najmniej jedna kopia zgodna w całości, brak wspólnej różnicy |
| `insufficient_copies` | `niepewne` | Znaleziono obrazy, ale za mało kopii tego samego ujęcia do porównania |
| `no_matches` | `niepewne` | Zdjęcia nie ma w indeksach wyszukiwarek |

**Ślady AI w samym pliku** ([app/core/image_provenance.py](app/core/image_provenance.py)) – odczytywane z oryginalnych bajtów, zanim usuniemy metadane:

| Źródło | Co sprawdzamy | Pewność |
|---|---|---|
| C2PA / Content Credentials (`c2pa-python`) | `digitalSourceType` w akcjach manifestu (także składników) i stan podpisu | najwyższa przy nienaruszonym podpisie (OpenAI, Adobe Firefly, Microsoft) |
| IPTC w XMP | `DigitalSourceType = trainedAlgorithmicMedia` / `compositeWithTrainedAlgorithmicMedia` | wysoka, ale bez podpisu |
| Parametry generatorów | PNG `parameters` (A1111), `prompt`/`workflow` (ComfyUI), InvokeAI, EXIF `UserComment`; nazwy generatorów tylko w polach „program” | wysoka, bez podpisu |
| Data najstarszej kopii | kopia w sieci sprzed 2022 r. → `predates_generative_ai` | tylko wskazówka, nie zmienia werdyktu |

`image_analysis.ai.result`: `ai_generated` → werdykt `fake_news` (pewność 0.95 z ważnym podpisem C2PA, 0.85 bez), `ai_edited` → werdykt `prawdziwe` obniżany do `niepewne`, `predates_generative_ai` / `no_signals` → bez zmian. Brak śladów niczego nie dowodzi – media społecznościowe i zrzuty ekranu usuwają metadane.

Dodatkowo: data najstarszej kopii z TinEye (`earliest_seen`, ostrzeżenie `archival_material` dla zdjęć starszych niż rok) i program do edycji z EXIF (`image_edit_software`). Wynik dla tych samych bajtów jest cache'owany (domyślnie 24 h), żeby nie odpytywać wyszukiwarek ponownie.

**Ograniczenia:** obrazy z AI bez metadanych (np. po zrzucie ekranu) nie zostaną rozpoznane; zdjęcia spoza indeksów wyszukiwarek nie zostaną porównane; subtelne zmiany o niskim kontraście mogą umknąć; scraping może przestać działać po zmianie stron wyszukiwarek. Zdjęcie trafia do Yandex (Rosja) i TinEye (Kanada).

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

- Backend sprawdza artykuły z URL oraz zdjęcia (`/checks/image`); nie ma endpointu dla czystego tekstu
- `pyproject.toml` nadpisuje wymaganie `lxml<6` z PicImageSearch (`override-dependencies`), bo trafilatura 2.3 wymaga lxml 6; PicImageSearch działa z lxml 6 poprawnie
- Wszystkie prompty są **wyłącznie po polsku**
- System zapisuje wyniki do SQLite (`data/prawdowid.db`)
- Limity zapytań: domyślnie 10/min na IP