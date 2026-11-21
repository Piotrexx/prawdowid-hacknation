# Prawdowid

Szybka i prosta weryfikacja informacji oparta na jawnym katalogu wiarygodnych źródeł.
Obywatel wkleja wiadomość, link albo zrzut ekranu na stronie WWW i dostaje
zwięzły wynik z cytatami ze źródeł, oceną siły podstawy i uczciwą informacją, czego nie udało się ustalić.

> Prototyp hackathonowy (wyzwanie MSZ „Prawdowid”). Nie jest oficjalną usługą.
> Zespół: Jan Skrobot, Dima Mehalatii, Piotr Łopatecki

## Co robi

- Wydziela z treści twierdzenia do sprawdzenia i oddziela fakty od opinii oraz prognoz.
- Szuka w lokalnym, polskojęzycznym korpusie **10 źródeł urzędowych** (maks. 10 dokumentów
  na źródło na przebieg – [docs/ZRODLA.md](docs/ZRODLA.md)).
- Po ekstrakcji słów kluczowych przez Bielika przeszukuje **pgvector** i dokłada do kontekstu
  artykuły o podobnym znaczeniu, które mogą opisywać to samo wydarzenie.
- Dla każdego twierdzenia zwraca jeden z wyników: **potwierdzone**, **fałszywe**, **wprowadzające w błąd**,
  **brak wystarczających dowodów**, **nie podlega weryfikacji**.
- Awarię, prośbę o doprecyzowanie i treść poza zakresem komunikuje osobno – to nie są werdykty.
- Każdy rozstrzygający wynik ma co najmniej jeden dosłowny cytat ze źródła (tytuł, wydawca, data, link).
  Cytaty są sprawdzane automatycznie; zmyślony cytat = brak werdyktu.
- Nierozstrzygnięte zgłoszenia trafiają do kolejki moderatora; podobne zgłoszenia są grupowane w jedną sprawę.
- Ignoruje i odnotowuje próby prompt injection, maskuje dane osobowe, nie zapisuje obrazów.

> **Uwaga:** obecnie działa tylko kanał WWW. Wymagania konkursu przewidują drugi kanał albo adapter
> demonstracyjny – trzeba go dodać przed oceną.

## Architektura w skrócie

```
frontend/  Next.js (kanał WWW, katalog źródeł, panel moderatora)
    │  HTTP/JSON
backend/   FastAPI
    ├─ api/                 kanał WWW i panel moderatora (+ ingest)
    ├─ core/pipeline.py     jedna logika weryfikacji, niezależna od kanału
    ├─ core/prompts.py      prompty Bielika i DeepSeeka (kontekst + fact-checki)
    ├─ ingest/              konektory 10 źródeł → tekst → embedding
    ├─ retrieval/           pgvector + hybrydowy rerank materiałów podobnych
    ├─ llm/                 wymienny dostawca modelu (API zgodne z OpenAI, domyślnie DeepSeek | Anthropic | brak)
    ├─ security/            PII, prompt injection, SSRF, limity żądań
    ├─ store/               PostgreSQL: sprawdzenia, korpus, przebiegi ingestu
    └─ data/                dane lokalne
```

`frontend/` i `backend/` to dwa niezależne projekty (osobne zależności, osobne uruchamianie, brak wspólnego
narzędzia typu monorepo). Szczegóły, przepływ danych i uzasadnienie wyborów: [docs/ARCHITEKTURA.md](docs/ARCHITEKTURA.md).

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

Pierwsze uruchomienie pobiera lokalny model embeddingów (ok. 470 MB). Ingest 10 źródeł
z limitem 10 dokumentów na źródło trwa ok. 2 minuty i tworzy ok. 80–100 dokumentów.

Bez klucza API usługa też się uruchomi: wyszukiwanie działa, a każde sprawdzenie kończy się jawnym
komunikatem o problemie technicznym (nigdy pozornym werdyktem) wraz z listą znalezionych materiałów.

Alternatywnie w kontenerach: `docker compose up --build` (wymaga pliku `backend/.env`).

### Scenariusz demonstracyjny

1. `http://localhost:3000` – wklej treść lub link, kliknij „Sprawdź”.
2. `http://localhost:3000/zrodla` – katalog źródeł z licencjami i zasadami kwalifikacji.
3. `http://localhost:3000/moderator` – kolejka spraw, statystyki, zdarzenia bezpieczeństwa, eksport CSV/JSON
   (token = `ADMIN_TOKEN`).

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
wyszukiwanie hybrydowe (BM25 + embeddingi) oraz walidator, który odrzuca odpowiedź modelu, gdy cytat nie
występuje w źródle. W Prawdowidzie ten walidator stał się podstawą reguł werdyktu.
