# Źródła

Korpus Prawdowida to **10 polskich źródeł urzędowych**, pobieranych automatycznie przez
`backend/app/ingest/`. Katalog źródeł jest w kodzie (`backend/app/ingest/registry.py`),
a stan korpusu i historia pobrań są widoczne w API (`GET /api/v1/admin/corpus/stats`)
oraz w `ingest_runs`.

## Co jest w korpusie

Stan po uruchomieniu `uv run python -m app.ingest.run --max 10`:
**10 źródeł, do 10 dokumentów na źródło** (ok. 80–100 dokumentów na przebieg).
Zapisujemy wyłącznie **tytuł, fragment do ok. 1500 znaków i link do oryginału** —
nie pełne teksty. Dzięki temu odpowiedź zawsze prowadzi do źródła, a prawo autorskie
nie jest naruszane.

| Klucz | Źródło | Co pobieramy | Sposób |
|---|---|---|---|
| `rcb-raport-dobowy` | Rządowe Centrum Bezpieczeństwa | dzienny raport dobowy | migawka strony, unikalna po dacie |
| `gov-ostrzezenia` | gov.pl – system ostrzeżeń (RSO) | komunikaty RSO dla 16 województw | oficjalne API JSON |
| `imgw-meteo` | IMGW-PIB – meteo | ostrzeżenia meteorologiczne | `danepubliczne.imgw.pl` (JSON) |
| `imgw-hydro` | IMGW-PIB – hydro | przekroczenia stanów wód; przy braku przekroczeń jawna migawka „brak przekroczeń” | `danepubliczne.imgw.pl` (JSON) |
| `cert-polska` | CERT Polska | komunikaty o oszustwach i podatnościach | lista HTML |
| `gddkia` | GDDKiA | aktualności | `gov.pl/web/gddkia/aktualnosci` |
| `kgpsp` | Komenda Główna PSP | aktualności | `gov.pl/web/kgpsp/aktualnosci` |
| `policja` | Policja | aktualności | `policja.pl/pol/aktualnosci` |
| `gis` | Główny Inspektorat Sanitarny | ostrzeżenia publiczne | `gov.pl/web/gis/ostrzezenia` |
| `paa` | Państwowa Agencja Atomistyki | aktualności | `gov.pl/web/paa/aktualnosci` |

### Świadome zamiany

- **GDDKiA** – oryginalne `drogi.gddkia.gov.pl` jest za WAF Incapsula i nie pozwala na
  stabilne pobieranie bez przeglądarki. Używamy oficjalnych aktualności GDDKiA na gov.pl.
- **PAA** – `monitoring.paa.gov.pl` to aplikacja Angular bez publicznego API.
  Używamy oficjalnych aktualności PAA na gov.pl. Monitoring radiacyjny można dodać później
  przez przeglądarkę headless lub API, jeśli zostanie udostępnione.
- **IMGW** – `meteo.imgw.pl` i `hydro.imgw.pl` to aplikacje JS; korzystamy z publicznych
  endpointów JSON IMGW, które zwracają te same dane.
- **Ostrzeżenia gov.pl** – strona jest aplikacją Vue; dane pobieramy z jej oficjalnego
  backendu `/api/data/proxy/rso/...`, a nie przez scraping DOM.

## Zasady pobierania

- `robots.txt` jest sprawdzany i respektowany; przy 401/403 źródło jest traktowane jako zablokowane.
- Maks. **10 dokumentów na źródło na jeden przebieg** (`--max`).
- Throttling **1 żądanie/s na domenę**, User-Agent `fact-check-research-bot/0.1`.
- Ochrona przed SSRF: wyłącznie publiczne adresy IP, bez przekierowań na sieci prywatne.
- Upsert po kanonicznym URL; `content_hash` (wydawca + tytuł + fragment) decyduje,
  czy przeliczać embedding.
- Migawki dzienne (RCB, hydro) mają URL z datą (`#2026-11-21`), więc historia nie znika.

## Embeddingi i wyszukiwanie

- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 wymiary),
  uruchamiany lokalnie przez `fastembed`/ONNX. Treść nie jest wysyłana do zewnętrznego API.
- Embedding liczony z: wydawca + tytuł + fragment. Dzięki temu krótkie komunikaty
  (np. IMGW) zachowują kontekst instytucji.
- Kandydaci: top 20, ostatnie 90 dni, z wyłączeniem sprawdzanego URL.
- Rerank hybrydowy: `0.8 * cosine + 0.2 * pokrycie słów kluczowych`.
- Wynik: maks. 6 materiałów, maks. 2 na źródło, z progiem podobieństwa
  (`RETRIEVAL_MIN_SIMILARITY`, `RETRIEVAL_STRONG_SIMILARITY`).

## Czego nie ma w korpusie

- Fact-checków redakcyjnych (Demagog, Konkret24, AFP) – to osobny kanał danych,
  planowany jako uzupełnienie, ale nie jest częścią tego MVP.
- Pełnych tekstów artykułów spoza gov.pl – świadomie tylko fragmenty i link.
- Platform społecznościowych – nigdy nie trafiają do korpusu.

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

- Dodać kanał fact-checkingowy (ClaimReview / Google Fact Check Tools) jako osobny typ źródła.
- Potwierdzić licencje fragmentów dla serwisów innych niż gov.pl.
- Dodać monitoring radiacyjny PAA przez przeglądarkę headless albo oficjalne API.
- Zbudować ręczny zbiór par „to samo wydarzenie / podobny temat” i dostroić progi retrievalu.
- Rozważyć mocniejszy model embeddingów (np. e5-large) po pomiarze jakości na polskich tekstach.
