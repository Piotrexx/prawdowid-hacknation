# Prawdowid – backend (FastAPI + PostgreSQL/pgvector)

Weryfikacja wiarygodności artykułu:
**URL → trafilatura → Bielik 4.5B (keywords) → [Google Fact Check + pgvector] → DeepSeek (verdict)**

Wynik zawiera nie tylko werdykt, ale też **materiały podobne semantycznie** z lokalnego korpusu
(10 źródeł urzędowych), które trafiają do kontekstu modelu oceniającego.

## Uruchomienie (Docker – zalecane)

```bash
cp backend/.env.example backend/.env     # uzupełnij klucze API
docker compose up --build
```

- Backend API: <http://localhost:8000>
- Dokumentacja OpenAPI: <http://localhost:8000/docs>
- Frontend: <http://localhost:3000>
- PostgreSQL + pgvector: `localhost:5432` (baza `prawdowid`, testowa `prawdowid_test`)
- Ollama (Bielik): <http://localhost:11434>

## Uruchomienie lokalne (bez Docker dla aplikacji)

```bash
# 1. Baza z pgvector
docker compose up -d postgres

# 2. Konfiguracja
cd backend
cp .env.example .env
# Wypełnij: LLM_API_KEY (DeepSeek), GOOGLE_FACTCHECK_API_KEY, ADMIN_TOKEN, ID_HASH_SALT

# 3. Zależności i serwer
uv sync
uv run uvicorn app.main:app --port 8000
```

Bielik działa przez Ollama/vLLM:

```bash
ollama pull bielik:4.5b-instruct
ollama serve
```

Bez klucza API usługa też się uruchomi: wyszukiwanie i korpus działają, a sprawdzenie kończy się
jawnym komunikatem o problemie technicznym (nigdy pozornym werdyktem).

## Baza danych i korpus

Wymagany jest PostgreSQL z rozszerzeniem `pgvector` (obraz `pgvector/pgvector:pg17`).
Schemat tworzy się automatycznie przy starcie (`CREATE EXTENSION IF NOT EXISTS vector` + `create_all`).

| Tabela | Zawartość |
|---|---|
| `checks` | przebieg sprawdzeń i pełna odpowiedź API |
| `security_events` | zdarzenia bezpieczeństwa |
| `articles` | dokumenty korpusu: tytuł, fragment, link, data, `embedding vector(384)` |
| `ingest_runs` | historia pobrań źródeł |

Embeddingi: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` przez `fastembed`
(384 wymiary, ok. 470 MB, działa lokalnie na CPU, bez wysyłania treści do zewnętrznego API).

### Ingest źródeł

```bash
uv run python -m app.ingest.run --list
uv run python -m app.ingest.run --only gis,cert-polska --max 10
uv run python -m app.ingest.run --max 10        # wszystkie źródła
```

Zasady: maks. 10 dokumentów na źródło na przebieg, `robots.txt` respektowany,
throttling 1 req/s na domenę, zapis tylko tytułu i fragmentu (nie pełnych tekstów),
upsert po URL i `content_hash` (embedding liczony ponownie tylko przy zmianie treści).

Źródła (szczegóły w [../docs/ZRODLA.md](../docs/ZRODLA.md)):

| Klucz | Źródło | Adapter |
|---|---|---|
| `rcb-raport-dobowy` | RCB – raport dobowy | migawka dzienna |
| `gov-ostrzezenia` | gov.pl – ostrzeżenia (RSO) | API JSON |
| `imgw-meteo` | IMGW – ostrzeżenia meteo | API JSON |
| `imgw-hydro` | IMGW – sytuacja hydrologiczna | API JSON |
| `cert-polska` | CERT Polska – komunikaty | lista HTML |
| `gddkia` | GDDKiA – aktualności (gov.pl) | lista HTML |
| `kgpsp` | KG PSP – aktualności | lista HTML |
| `policja` | Policja – aktualności | lista HTML |
| `gis` | GIS – ostrzeżenia | lista HTML |
| `paa` | PAA – aktualności | lista HTML |

Ingest można też uruchomić z panelu admina:

```http
POST /api/v1/admin/corpus/ingest        # X-Admin-Token, opcjonalnie {"sources": ["gis"], "max_per_source": 10}
GET  /api/v1/admin/corpus/stats
```

## Wyszukiwanie semantyczne

Po ekstrakcji słów kluczowych Bielik podaje `keywords`, `main_topic` i `summary`.
Zapytanie do pgvector powstaje z tych trzech pól. Kandydaci (top 20, ostatnie 90 dni)
są przenoszani przez hybrydowy rerank:

```
score = 0.8 * cosine_similarity + 0.2 * keyword_overlap
```

Wymagane jest podobieństwo ≥ `RETRIEVAL_MIN_SIMILARITY` (domyślnie 0.58) oraz
albo wspólne słowo kluczowe, albo bardzo wysokie podobieństwo
(`RETRIEVAL_STRONG_SIMILARITY`, domyślnie 0.82). Wynik: maks. 6 materiałów,
maks. 2 z jednego źródła. Trafienia trafiają do `related_materials` w odpowiedzi API
oraz do promptu DeepSeek jako **kontekst, nie dowód**.

## API (`/api/v1`)

| Metoda | Ścieżka | Opis |
|---|---|---|
| POST | `/checks` | Sprawdzenie URL artykułu (`{url, session_id?}`) |
| GET | `/checks/{id}` | Zapisany wynik |
| DELETE | `/sessions/{session_id}` | Usunięcie danych sesji |
| GET | `/health` | Stan usługi, modele, liczba dokumentów korpusu |
| GET | `/admin/metrics`, `/admin/checks`, `/admin/export` | Panel admina (`X-Admin-Token`) |
| POST | `/admin/corpus/ingest` | Ingest w tle |
| GET | `/admin/corpus/stats` | Statystyki korpusu i przebiegów |

## Testy

Testy wymagają PostgreSQL z pgvector (baza `prawdowid_test`, tworzona przez `backend/db/init.sql`):

```bash
docker compose up -d postgres
cd backend
uv run pytest
uv run ruff check .
```

Testy nie łączą się z internetem: adaptery są sprawdzane na fixture'ach HTML/JSON,
a w pipeline'ie używane są fake providery LLM i `FakeEmbedder`.

## Struktura projektu

```
backend/
├── app/
│   ├── api/              # checks.py, admin.py, deps.py
│   ├── core/             # pipeline.py, prompts.py
│   ├── ingest/           # registry.py, adapters.py, http.py, run.py
│   ├── retrieval/        # embeddings.py, corpus.py, service.py
│   ├── llm/              # providerzy OpenAI-compatible
│   ├── security/         # SSRF, robots.txt, rate limiting
│   ├── store/            # models.py, db.py
│   ├── config.py
│   ├── schemas.py
│   └── main.py
├── db/init.sql           # CREATE EXTENSION vector + baza testowa
├── data/                 # dane lokalne
├── eval/                 # ewaluacja na prawdziwym modelu
├── tests/
├── Dockerfile
└── pyproject.toml
```

## Wymagane klucze API

1. DeepSeek API – <https://platform.deepseek.com/> (werdykt)
2. Google Fact Check Tools API – <https://developers.google.com/fact-check/tools/api>
3. Ollama + Bielik – `ollama pull bielik:4.5b-instruct` (słowa kluczowe)

## Uwagi

- Backend przyjmuje **tylko URL** (brak endpointu dla czystego tekstu i obrazów).
- Prompty są wyłącznie po polsku.
- Limity zapytań: domyślnie 10/min na IP.
- Pierwsze sprawdzenie po starcie może potrwać dłużej, jeśli model embeddingów nie jest jeszcze w cache.
