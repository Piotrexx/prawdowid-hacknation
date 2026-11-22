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

`docker-compose.yml` uruchamia PostgreSQL/pgvector, backend, Ollamę z Bielikiem,
frontend oraz bota Discord. Modele embeddingów i Whisper są cache'owane w wolumenie
`backend-var`.

## Endpointy

Publiczne:

- `POST /api/v1/checks` — tekst lub URL
- `POST /api/v1/checks/image` — zrzut ekranu/zdjęcie: odczyt tekstu (OCR) + analiza obrazu
- `POST /api/v1/checks/audio` — nagranie (webm/wav/ogg)
- `POST /api/v1/channels/demo` — adapter demonstracyjnego drugiego kanału (ta sama ścieżka weryfikacji)
- `GET /api/v1/checks/{id}`
- `GET /api/v1/health`
- `POST /api/v1/consent`, `GET /api/v1/consent/{session_id}`
- `DELETE /api/v1/sessions/{session_id}`
- `POST /api/v1/archive`, `GET /api/v1/archive/{id}`, `DELETE /api/v1/archive/{id}`

Wszystkie zapisy sprawdzeń i archiwum wymagają aktywnej zgody na aktualną wersję
polityki prywatności (ciasteczko + wpis w bazie). Brak zgody to `428`, nie werdykt.

Panel moderatora (konto e-mail/hasło albo zgodnościowo `X-Admin-Token`):

- `POST /api/v1/admin/auth/login`, `POST /api/v1/admin/auth/logout`
- `GET/PATCH /api/v1/admin/auth/me` — konto, ustawienia powiadomień, historia opinii i zmian
- `POST /api/v1/admin/auth/me/password`
- `GET /api/v1/admin/auth/me/push-public-key`, `POST/DELETE /api/v1/admin/auth/me/push-subscription`
- `GET/POST /api/v1/admin/moderators`, `PATCH /api/v1/admin/moderators/{id}`,
  `POST /api/v1/admin/moderators/{id}/reset-password` (superużytkownik)
- `GET /api/v1/admin/metrics`
- `GET /api/v1/admin/checks`, `GET /api/v1/admin/events`
- `GET /api/v1/admin/graph` - mapa wydarzeń (węzły, relacje, kotwice; `window_days`, `include_proposed`)
- `GET /api/v1/admin/graph/events/{id}` - wydarzenie z obserwacjami i relacjami
- `PATCH /api/v1/admin/graph/events/{id}/members/{member_id}` - akceptacja/odrzucenie kandydata
- `PATCH /api/v1/admin/graph/links/{id}` - akceptacja/odrzucenie relacji
- `POST /api/v1/admin/graph/events/{id}/merge` - scalenie wydarzeń
- `POST /api/v1/admin/graph/events/{id}/members/{member_id}/split` - wydzielenie obserwacji
- `POST /api/v1/admin/graph/rebuild` - przebudowa mapy z zapisanych zgłoszeń (superużytkownik)
- `GET /api/v1/public/event-map` - publiczna, zagregowana mapa (próg k-anonimowości)
- `GET/PATCH /api/v1/admin/cases` — każdy moderator może poprawić treść, wagę i status
- `GET/POST /api/v1/admin/cases/{id}/comments`, `GET/POST /api/v1/admin/articles/{id}/comments`,
  `DELETE /api/v1/admin/comments/{id}`
- `GET/PUT /api/v1/admin/llm/providers`, `GET/PUT /api/v1/admin/llm/settings`
- `GET /api/v1/admin/export?format=csv|json`
- `GET /api/v1/admin/export/stix`
- `POST /api/v1/admin/corpus/ingest`, `GET /api/v1/admin/corpus/stats`
- `GET/DELETE /api/v1/admin/archive`

Pierwsze konto superużytkownika powstaje przy starcie z `MODERATOR_BOOTSTRAP_EMAIL`
(bez hasła zostanie ono wygenerowane i wypisane w logu) albo przez:

```bash
uv run python scripts/create_superuser.py --email admin@prawdowid.pl
```

Skrypt wypisuje jednorazowy link `…/moderator#token=…`, który od razu loguje do panelu,
i domyślnie otwiera go w przeglądarce. Przy lokalnym starcie taki link pojawia się też
w logu, gdy konto zostało właśnie utworzone z `.env`. Flaga `--no-open` zostawia tylko
link, a `--no-link` pomija link.

Powiadomienia o komentarzach są opcjonalne i włączane w profilu każdego konta:
Discord (webhook wspólny lub prywatny), e-mail (SMTP) i Web Push (VAPID).
Wysyłamy je, gdy sprawa albo artykuł osiągnie ustawiony próg opinii (domyślnie 2).

Nie ma publicznego endpointu `/sources`; katalog źródeł jest w kodzie i służy do
audytu oraz metadanych cytowań.

### Weryfikacja zdjęć

Jedno żądanie do `/api/v1/checks/image` uruchamia równolegle trzy rzeczy. OCR jest
niezależny od analizy obrazu: awaria wyszukiwarek obrazów nie przerywa sprawdzenia,
dodaje tylko ostrzeżenie, a werdykt twierdzeń liczy się dalej.

1. **OCR** — model odczytuje tekst widoczny na obrazie; ten tekst przechodzi tę samą
   weryfikację twierdzeń co wklejona wiadomość.
2. **Odwrotne wyszukiwanie** ([PicImageSearch](https://github.com/kitUIN/PicImageSearch),
   scraping) — Yandex i TinEye równolegle, do 10 kopii. Pełny obraz ze strony źródłowej
   pobieramy z ochroną SSRF jak przy artykułach; w razie błędu bierzemy miniaturę.
   Awaria jednego silnika daje ostrzeżenie, wszystkich — ostrzeżenie zamiast werdyktu
   o obrazie.
3. **Porównanie** ([app/core/image_compare.py](app/core/image_compare.py)) —
   dopasowanie kopii do zdjęcia (SIFT + RANSAC, obsługuje kadrowanie i skalowanie),
   dopasowanie jasności i kontrastu z pominięciem odstających pikseli, różnica w siatce
   8×8. Globalny hash (pHash) **nie wystarcza** — doklejony obiekt zmienia go o 1–2 bity.
   Zdjęcie jest podejrzane, gdy **w tym samym miejscu** różni się od większości
   (≥60%, min. 2) kopii; różnice tylko w pojedynczych kopiach (podpisy, znaki wodne)
   nie są brane pod uwagę.

| `image_analysis.assessment` | Wpływ na werdykt | Znaczenie |
|---|---|---|
| `manipulation_suspected` | `falszywe` | Fragment różni się od większości kopii; `changed_regions` wskazuje gdzie (współrzędne 0–1) |
| `consistent_with_copies` | bez zmian | Co najmniej jedna kopia zgodna w całości, brak wspólnej różnicy |
| `insufficient_copies` | bez zmian | Znaleziono obrazy, ale za mało kopii tego samego ujęcia do porównania |
| `no_matches` | bez zmian | Zdjęcia nie ma w indeksach wyszukiwarek |

**Ślady AI w samym pliku** ([app/core/image_provenance.py](app/core/image_provenance.py))
— odczytywane z oryginalnych bajtów, zanim usuniemy metadane:

| Źródło | Co sprawdzamy | Pewność |
|---|---|---|
| C2PA / Content Credentials (`c2pa-python`) | `digitalSourceType` w akcjach manifestu (także składników) i stan podpisu | najwyższa przy nienaruszonym podpisie (OpenAI, Adobe Firefly, Microsoft) |
| IPTC w XMP | `DigitalSourceType = trainedAlgorithmicMedia` / `compositeWithTrainedAlgorithmicMedia` | wysoka, ale bez podpisu |
| Parametry generatorów | PNG `parameters` (A1111), `prompt`/`workflow` (ComfyUI), InvokeAI, EXIF `UserComment`; nazwy generatorów tylko w polach „program” | wysoka, bez podpisu |
| Data najstarszej kopii | kopia w sieci sprzed 2022 r. → `predates_generative_ai` | tylko wskazówka, nie zmienia werdyktu |

`image_analysis.ai.result`: `ai_generated` → werdykt `falszywe` (pewność 0.95 z ważnym
podpisem C2PA, 0.85 bez), `ai_edited` → werdykt `potwierdzone` obniżany do
`brak_wystarczajacych_dowodow`, `predates_generative_ai` / `no_signals` → bez zmian.
Brak śladów niczego nie dowodzi — media społecznościowe i zrzuty ekranu usuwają metadane.

Dodatkowo: data najstarszej kopii z TinEye (`earliest_seen`, ostrzeżenie
`archival_material` dla zdjęć starszych niż rok) i program do edycji z EXIF
(`image_edit_software`). Zdjęcie jest wysyłane do wyszukiwarek bez metadanych EXIF;
samego pliku nie zapisujemy w bazie.

| Zmienna | Znaczenie |
|---|---|
| `IMAGE_SEARCH_ENGINES` | Silniki odwrotnego wyszukiwania (domyślnie `yandex,tineye`; `bing` jest niedostępny w PicImageSearch 3.12.11) |
| `IMAGE_SEARCH_TIMEOUT_S` | Limit czasu jednego silnika (domyślnie 25 s) |
| `IMAGE_CACHE_HOURS` | Jak długo wynik dla tych samych bajtów zdjęcia jest brany z bazy |
| `IMAGE_MAX_BYTES` | Limit rozmiaru przesłanego pliku (domyślnie 5 MB) |

**Ograniczenia analizy obrazu:** obrazy z AI bez metadanych (np. po zrzucie ekranu) nie
zostaną rozpoznane; zdjęcia spoza indeksów wyszukiwarek nie zostaną porównane; subtelne
zmiany o niskim kontraście mogą umknąć; scraping może przestać działać po zmianie stron
wyszukiwarek. Zdjęcie trafia do Yandex (Rosja) i TinEye (Kanada).

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
- Porównanie zdjęć wykrywa doklejone, usunięte lub zmienione fragmenty względem kopii
  w sieci; nie oceni zdjęć, których nie ma w indeksach wyszukiwarek. Media
  społecznościowe i zrzuty ekranu usuwają metadane, więc brak śladów AI niczego nie
  wyklucza.
- Wyszukiwarki obrazów bywają niedostępne (captcha, limity); wynik opiera się wtedy na
  tych, które odpowiedziały.
- Nawet niezmienione zdjęcie może zostać użyte w fałszywym kontekście.
- Archiwum przechowuje tylko fragment i metadane, nie pełne treści chronione prawem
  autorskim.
- Integracja z OpenCTI jest eksportem STIX (plik), nie synchronicznym push do
  instancji.
- `pyproject.toml` nadpisuje wymaganie `lxml<6` z PicImageSearch
  (`override-dependencies`), bo trafilatura 2.3 wymaga lxml 6; PicImageSearch działa
  z lxml 6 poprawnie.
