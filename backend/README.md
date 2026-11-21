# Prawdowid — backend

Weryfikacja informacji oparta na jawnym korpusie źródeł i cytatach. Każde twierdzenie
jest oceniane osobno; werdykt wynika z cytatów zweryfikowanych automatycznie w źródle
(`app/core/verdict.py`). Model językowy proponuje ocenę, ale nie jest jedyną podstawą
werdyktu. Gdy brakuje dowodów, usługa wstrzymuje się od rozstrzygnięcia.

## Architektura

- **FastAPI** — jeden kontrakt API dla WWW, obrazów i nagrań.
- **PostgreSQL + pgvector** — jedyne źródło prawdy dla przebiegu sprawdzeń, spraw
  moderatora, zgód, archiwum, korpusu i przebiegów ingestu.
- **Ingest w kodzie** (`app/ingest/registry.py`) — źródła urzędowe, prawne i
  fact-checkingowe są pobierane na bieżąco i zapisywane w tabeli `articles`.
  Nie ma pliku `sources.yaml` ani statycznego korpusu JSONL.
- **Wyszukiwanie** — embeddingi fastembed + pgvector; przy braku embeddingów działa
  uczciwy fallback leksykalny.
- **Model językowy** — wymienny dostawca (`openai_compatible` lub `anthropic`);
  Bielik lokalnie odpowiada za słowa kluczowe.
- **Głos** — nagranie jest przesyłane na serwer i transkrybowane lokalnie przez
  faster-whisper; dźwięk nie jest zapisywany.
- **Archiwum** — kontrolowana, ograniczona retencją kopia fragmentu materiału,
  wyłącznie na wyraźne żądanie użytkownika i po zgodzie na politykę prywatności.
- **Eksport** — CSV, JSON i bundle STIX 2.1 z przybliżonym mapowaniem DISARM.

## Uruchomienie

```bash
# 1. Baza z pgvector
docker compose up -d postgres

# 2. Zależności
cd backend
uv sync

# 3. Konfiguracja
cp .env.example .env
# uzupełnij LLM_API_KEY (opcjonalnie GOOGLE_FACTCHECK_API_KEY, ADMIN_TOKEN)

# 4. Ingest źródeł (wymaga sieci)
uv run python -m app.ingest.run --max 10

# 5. Usługa
uv run uvicorn app.main:app --reload --port 8000
```

Bez ingestu usługa odpowiada, ale korpus jest pusty i twierdzenia kończą się
„brak wystarczających dowodów”. To poprawne zachowanie, nie werdykt.

### Docker

```bash
docker compose up --build
```

`docker-compose.yml` uruchamia PostgreSQL/pgvector, backend, Ollamę z Bielikiem i
frontend. Modele embeddingów i Whisper są cache'owane w wolumenie `backend-var`.

## Endpointy

Publiczne:

- `POST /api/v1/checks` — tekst lub URL
- `POST /api/v1/checks/image` — zrzut ekranu/zdjęcie
- `POST /api/v1/checks/audio` — nagranie (webm/wav/ogg)
- `GET /api/v1/checks/{id}`
- `GET /api/v1/health`
- `POST /api/v1/consent`, `GET /api/v1/consent/{session_id}`
- `DELETE /api/v1/sessions/{session_id}`
- `POST /api/v1/archive`, `GET /api/v1/archive/{id}`, `DELETE /api/v1/archive/{id}`

Wszystkie zapisy sprawdzeń i archiwum wymagają aktywnej zgody na aktualną wersję
polityki prywatności (ciasteczko + wpis w bazie). Brak zgody to `428`, nie werdykt.

Panel moderatora (`X-Admin-Token`):

- `GET /api/v1/admin/metrics`
- `GET /api/v1/admin/checks`, `GET /api/v1/admin/events`
- `GET/PATCH /api/v1/admin/cases`
- `GET /api/v1/admin/export?format=csv|json`
- `GET /api/v1/admin/export/stix`
- `POST /api/v1/admin/corpus/ingest`, `GET /api/v1/admin/corpus/stats`
- `GET/DELETE /api/v1/admin/archive`

Nie ma publicznego endpointu `/sources`; katalog źródeł jest w kodzie i służy do
audytu oraz metadanych cytowań.

## Źródła i aktualizacja

Katalog źródeł znajduje się w `app/ingest/registry.py`. Każdy wpis ma nazwę,
wydawcę, typ, poziom (1–3), licencję, politykę przechowywania, uzasadnienie
kwalifikacji i sposób aktualizacji. Ingest respektuje robots.txt i nie obchodzi
zabezpieczeń serwisów. Źródła fact-checkingowe (ClaimReview) trafiają do korpusu
jako dane strukturalne: twierdzenie, ocena i link.

Status źródła (np. sankcje UE) jest osobnym, neutralnym ostrzeżeniem w
`app/security/source_status.py`; nigdy nie przesądza o prawdziwości treści.

## Prywatność i bezpieczeństwo

- Maskowanie oczywistych danych osobowych przed wysłaniem do modelu.
- Minimalizacja: dla stron zapisujemy tylko początek treści; nagrań nie zapisujemy.
- Retencja sprawdzeń `RETENTION_DAYS`, archiwum `ARCHIVE_RETENTION_DAYS`; usuwanie
  sesji usuwa sprawdzenia, zgodę, powiązania spraw i archiwum.
- Instrukcje w treści i źródłach są traktowane jako dane; prompt injection jest
  wykrywany i logowany, ale nigdy nie zmienia zasad systemu.
- Sekrety wyłącznie w `.env`; `.env` nie trafia do repozytorium.

## Testy

```bash
docker compose up -d postgres
cd backend
uv run pytest
uv run ruff check app tests
```

Testy wymagają PostgreSQL z pgvector (`prawdowid_test`). `backend/eval/cases.jsonl`
zawiera ≥30 przypadków referencyjnych; `uv run python -m eval.run_eval` mierzy
macro-F1, pokrycie cytowań, wstrzymanie się, odporność na prompt injection,
spójność i czas odpowiedzi.

## Ograniczenia

- Korpus zależy od dostępności źródeł i działania ingestu.
- Model językowy może się mylić; cytaty są weryfikowane, ale interpretacja nie jest
  nieomylna.
- Transkrypcja lokalna może zawierać błędy; nie oceniamy autentyczności nagrania.
- Archiwum przechowuje tylko fragment i metadane, nie pełne treści chronione prawem
  autorskim.
- Integracja z OpenCTI jest eksportem STIX (plik), nie synchronicznym push do
  instancji.
