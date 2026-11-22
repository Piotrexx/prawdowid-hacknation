# Źródła

Korpus Prawdowida jest budowany na bieżąco przez `backend/app/ingest/` i zapisywany
w PostgreSQL (tabela `articles`). Katalog źródeł jest **w kodzie**
(`backend/app/ingest/registry.py`) — nie ma pliku `sources.yaml` ani statycznego
korpusu JSONL. Stan korpusu i historia pobrań są widoczne w
`GET /api/v1/admin/corpus/stats` (nagłówek `X-Admin-Token`).

## Typy źródeł i poziomy

- **Poziom 1 — źródła pierwotne/urzędowe:** RCB, RSO gov.pl, IMGW, CERT Polska,
  GDDKiA, KG PSP, Policja, GIS, PAA, MSZ, Sejm ELI, OSW. Mają największą wagę w
  ocenie siły dowodów.
- **Poziom 2 — fact-checking:** Konkret24 (RSS), Pravda (RSS i rekordy ClaimReview),
  FakeNews.pl (RSS). Records ClaimReview zapisują twierdzenie, ocenę redakcji,
  link i adresy wcześniejszych wystąpień.
- **Poziom 3 — media:** Rzeczpospolita. Mogą dawać wyłącznie kontekst; nigdy same
  nie rozstrzygają werdyktu.

Każdy wpis `SourceSpec` zawiera nazwę, wydawcę, typ, poziom, licencję, politykę
przechowywania (`full_text`, `excerpt`, `structured`), uzasadnienie kwalifikacji i
sposób aktualizacji. Dzięki temu lista źródeł jest audytowalna w repozytorium.

## Co jest w korpusie

- Tytuł, treść lub fragment zależnie od licencji, wydawca, data publikacji, data
  pobrania i link do oryginału.
- Dla źródeł na otwartych licencjach i materiałów urzędowych — pełny tekst.
- Dla treści chronionych prawem autorskim — tylko tytuł, krótki fragment i link.
- Dla ClaimReview — dane strukturalne: twierdzenie, ocena, link, `appearance_urls`.

Nie przechowujemy pełnych treści ani obrazów bez podstawy prawnej, licencji,
retencji i procedury usunięcia.

## Zasady pobierania

- `robots.txt` jest sprawdzany i respektowany; przy 401/403 źródło jest pomijane.
- Maks. `INGEST_MAX_PER_SOURCE` dokumentów na źródło na przebieg (`--max`).
- Throttling `INGEST_REQUEST_DELAY_S` na domenę, User-Agent `fact-check-research-bot/0.1`.
- Ochrona przed SSRF: wyłącznie publiczne adresy IP, bez przekierowań na sieci prywatne.
- Upsert po `external_id` (źródło + URL + twierdzenie); `content_hash` decyduje,
  czy przeliczać embedding.
- Migawki dzienne (RCB, hydro) mają URL z datą, więc historia nie znika.

## Embeddingi i wyszukiwanie

- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 wymiary),
  lokalnie przez `fastembed`/ONNX. Treść nie jest wysyłana do zewnętrznego API.
- Embedding liczony z: wydawca + tytuł + treść/fragment.
- Kandydaci: pgvector (HNSW, cosine), `RETRIEVAL_CANDIDATES`; bez filtra wieku, żeby
  materiał archiwalny mógł wywołać ostrzeżenie zamiast zniknąć.
- Rerank: `0.8 * cosine + 0.2 * pokrycie słów kluczowych`; maks. `RETRIEVAL_TOP_K`
  fragmentów, maks. `RETRIEVAL_MAX_PER_SOURCE` na źródło.
- Gdy embeddingi są wyłączone lub model się nie wczyta, działa fallback leksykalny;
  odpowiedź zawiera ostrzeżenie `retrieval_degraded`.

## Status źródła i incydenty

- `app/security/source_status.py` zawiera jawną listę statusów (np. sankcje UE) i
  podstawę prawną. Status wywołuje neutralne ostrzeżenie i nigdy nie przesądza o
  prawdziwości konkretnej treści.
- Dopasowania do znanych incydentów (URL, domena po ≥3 przypadkach, podobieństwo
  treści) są pokazywane jako kontekst, nie jako werdykt.

## Aktualizacja

```bash
cd backend
uv run python -m app.ingest.run                    # wszystkie źródła
uv run python -m app.ingest.run --only gis,cert-polska --max 10
uv run python -m app.ingest.run --list             # lista kluczy
```

W Dockerze ingest można uruchomić z panelu moderatora:
`POST /api/v1/admin/corpus/ingest` (nagłówek `X-Admin-Token`).

## Do zrobienia przed pilotażem

- Potwierdzić licencje fragmentów dla serwisów innych niż gov.pl.
- Dodać monitoring radiacyjny PAA przez przeglądarkę headless albo oficjalne API.
- Zbudować ręczny zbiór par „to samo wydarzenie / podobny temat” i dostroić progi.
- Rozważyć mocniejszy model embeddingów (np. e5-large) po pomiarze jakości.
