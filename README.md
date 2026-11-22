# Prawdowid

Szybka i prosta weryfikacja informacji oparta na jawnym katalogu wiarygodnych źródeł.
Obywatel wkleja wiadomość, link albo zrzut ekranu na stronie WWW i dostaje
zwięzły wynik z cytatami ze źródeł, oceną siły podstawy i uczciwą informacją, czego nie udało się ustalić.

> Prototyp hackathonowy (wyzwanie MSZ „Prawdowid”). Nie jest oficjalną usługą.
> Zespół: Jan Skrobot, Dima Mehalatii, Piotr Łopatecki

## Co robi

- Wydziela z treści twierdzenia do sprawdzenia i oddziela fakty od opinii oraz prognoz.
- Szuka w polskojęzycznym korpusie **źródeł urzędowych, prawnych i fact-checkingowych**
  (maks. `INGEST_MAX_PER_SOURCE` dokumentów na źródło na przebieg – [docs/ZRODLA.md](docs/ZRODLA.md)).
- Każde twierdzenie jest osobno zestawiane z fragmentami źródeł przez **PostgreSQL + pgvector**
  i reguły werdyktu; przy braku embeddingów działa jawny fallback leksykalny.
- Dla każdego twierdzenia zwraca jeden z wyników: **potwierdzone**, **fałszywe**, **wprowadzające w błąd**,
  **brak wystarczających dowodów**, **nie podlega weryfikacji**.
- Awarię, prośbę o doprecyzowanie i treść poza zakresem komunikuje osobno – to nie są werdykty.
- Każdy rozstrzygający wynik ma co najmniej jeden dosłowny cytat ze źródła (tytuł, wydawca, data, link).
  Cytaty są sprawdzane automatycznie; zmyślony cytat = brak werdyktu.
- Nierozstrzygnięte zgłoszenia trafiają do kolejki moderatora; podobne zgłoszenia są grupowane w jedną sprawę.
- Ignoruje i odnotowuje próby prompt injection, maskuje dane osobowe, nie zapisuje obrazów.

> **Drugi kanał:** `POST /api/v1/channels/demo` to adapter demonstracyjny, który woła tę samą
> ścieżkę weryfikacji co WWW (spójność wyniku i cytatów jest testowana).

## Architektura w skrócie

```
frontend/  Next.js (kanał WWW, katalog źródeł, panel moderatora)
    │  HTTP/JSON
backend/   FastAPI
    ├─ api/                 kanał WWW i panel moderatora (+ ingest)
    ├─ core/pipeline.py     jedna logika weryfikacji, niezależna od kanału
    ├─ core/events.py       mapa wydarzeń: klastry zgłoszeń i relacje między nimi
    ├─ core/prompts.py      prompty Bielika i DeepSeeka (kontekst + fact-checki)
    ├─ ingest/              konektory źródeł → tekst → embedding → PostgreSQL
    ├─ retrieval/           pgvector + rerank; fallback leksykalny
    ├─ llm/                 wymienny dostawca modelu (API zgodne z OpenAI, domyślnie DeepSeek | Anthropic | brak)
    ├─ security/            PII, prompt injection, SSRF, statusy źródeł, limity żądań
    ├─ integrations/        eksport STIX 2.1 + mapowanie DISARM
    └─ store/               PostgreSQL: sprawdzenia, sprawy, zgody, archiwum, korpus, ingest
```

`frontend/` i `backend/` to dwa niezależne projekty (osobne zależności, osobne uruchamianie, brak wspólnego
narzędzia typu monorepo). Szczegóły, przepływ danych i uzasadnienie wyborów: [docs/ARCHITEKTURA.md](docs/ARCHITEKTURA.md).

## Mapa wydarzeń

Zapisane zgłoszenia (wyłącznie po zgodzie na politykę prywatności) są łączone w **wydarzenia** —
klastry twierdzeń o tej samej sytuacji. Mapa pokazuje też relacje między wydarzeniami
(kolejny etap, sprzeczność, wspólny temat lub podmiot) oraz kotwice do znanych incydentów
z korpusu fact-checkingowego.

- **Panel moderatora → „Mapa wydarzeń”**: oś czasu, graf, kandydaci do akceptacji, scalanie,
  wydzielanie obserwacji i eksport śladu decyzji do audytu.
- **Publiczna `/mapa`**: wyłącznie zagregowane wydarzenia z co najmniej
  `EVENT_PUBLIC_MIN_MEMBERS` zgłoszeniami. Bez treści zgłoszeń, numerów sesji i danych osobowych.
- **Łączenie**: pgvector po twierdzeniach + fallback leksykalny. Pary o wysokiej pewności są
  akceptowane automatycznie, szara strefa trafia do moderatora. Opcjonalny kwalifikator LLM
  (`EVENT_LLM_QUALIFIER_ENABLED`) ocenia tylko szarą strefę i musi wskazać dosłowne cytaty.
- **Zasada**: przynależność do wydarzenia jest kontekstem analitycznym. Werdykt nadal wynika
  wyłącznie z cytatów w źródłach (`claims`). Fałszywe połączenie jest gorsze niż brak połączenia.

Konfiguracja progów i limitów: `EVENT_*` w [backend/.env.example](backend/.env.example).
Administrator może przebudować mapę z zapisanych zgłoszeń (`POST /api/v1/admin/graph/rebuild`).

## Uruchomienie

Wymagania: [uv](https://docs.astral.sh/uv/) (sam pobierze Pythona 3.13), Node.js 20+, Docker
(dla PostgreSQL + pgvector), klucz API modelu.

```bash
# 1. Baza danych – PostgreSQL z pgvector (port 5432)
docker compose up -d postgres

# 2. Backend – http://localhost:8000 (dokumentacja API: /docs)
cd backend
cp .env.example .env        # uzupełnij LLM_API_KEY (klucz DeepSeek), ADMIN_TOKEN, ID_HASH_SALT
uv sync
uv run python -m app.ingest.run --max 10   # opcjonalnie: od razu zbuduj korpus
uv run uvicorn app.main:app --port 8000

# 3. Frontend – http://localhost:3000
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Pierwsze uruchomienie pobiera lokalny model embeddingów (ok. 470 MB) oraz model Whisper
(dla nagrań). Ingest źródeł z limitem dokumentów na źródło tworzy korpus w PostgreSQL.

Bez klucza API usługa też się uruchomi: wyszukiwanie działa, a każde sprawdzenie kończy się jawnym
komunikatem o problemie technicznym (nigdy pozornym werdyktem) wraz z listą znalezionych materiałów.

Alternatywnie w kontenerach: `docker compose up --build` (wymaga pliku `backend/.env`).

### Scenariusz demonstracyjny

1. `http://localhost:3000` – wklej treść, link, zrzut ekranu albo nagraj głos; kliknij „Sprawdź”.
2. `http://localhost:3000/moderator` – kolejka spraw, statystyki, zdarzenia bezpieczeństwa,
   archiwum i eksport CSV/JSON/STIX (token = `ADMIN_TOKEN`).
3. Po zaakceptowaniu polityki prywatności sprawdzenia i archiwum są zapisywane w PostgreSQL;
   usunięcie sesji usuwa powiązane dane.

## Testy i mierniki

```bash
docker compose up -d postgres
cd backend
uv run pytest                      # testy bez sieci (fake LLM + FakeEmbedder, realny PostgreSQL)
uv run python -m eval.run_eval     # mierniki z sekcji 6 na prawdziwym modelu (kosztuje!)
```

Opis scenariuszy A–J, sposób liczenia mierników i stan pomiarów: [docs/TESTY-I-RYZYKA.md](docs/TESTY-I-RYZYKA.md).

## Dokumenty

| Dokument | Zawartość |
|---|---|
| [docs/ARCHITEKTURA.md](docs/ARCHITEKTURA.md) | architektura, przepływ danych, modele i dostawcy, bezpieczeństwo, prywatność, koszty, ograniczenia |
| [docs/ZRODLA.md](docs/ZRODLA.md) | źródła, licencje, kwalifikacja, aktualizacja, wykluczenia |
| [docs/TESTY-I-RYZYKA.md](docs/TESTY-I-RYZYKA.md) | testy wg sekcji 6, nieobsługiwane przypadki, lista ryzyk |
| [backend/README.md](backend/README.md) | konfiguracja, API, aktualizacja korpusu |
| [frontend/README.md](frontend/README.md) | uruchomienie i widoki interfejsu |

## Pochodzenie

Projekt rozwija pomysły z [ellmu](https://github.com/Piotrexx/ellmu): pobieranie artykułów (trafilatura),
wyszukiwanie semantyczne oraz walidator, który odrzuca odpowiedź modelu, gdy cytat nie występuje w źródle.
W Prawdowidzie ten walidator stał się podstawą reguł werdyktu.
