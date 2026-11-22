# Testy, ograniczenia i ryzyka

## Stan pomiarów

| Co | Stan |
|---|---|
| Testy automatyczne (`uv run pytest`) | **47/47 przechodzi.** Wymagają PostgreSQL z pgvector (`docker compose up -d postgres`). Model jest w nich podstawiony (fake LLM + `FakeEmbedder`), więc sprawdzają logikę, reguły, bezpieczeństwo, ingest i retrieval – nie jakość modelu. |
| Żądania do dostawców modelu | Kształt żądań (API zgodne z OpenAI, w tym tryb `json_object` używany przez DeepSeek, oraz Anthropic) oraz obsługa odmowy, uciętej odpowiedzi, limitu i błędów są sprawdzone na atrapie transportu HTTP – **nie na prawdziwym API**. |
| Wyszukiwanie na prawdziwym korpusie | Sprawdzone na 157 dokumentach z 18 źródeł (tryb hybrid: pgvector + BM25). Zapytanie hydrologiczne trafia na komunikaty IMGW i raport RCB; zapytanie spoza korpusu nie zwraca trafień. |
| Ścieżka bez klucza API (scenariusz J) | Sprawdzona na działającym serwerze: status `error`, brak werdyktu, lista materiałów. |
| **Mierniki z sekcji 6 na prawdziwym modelu** | **Zmierzone** – model: `openai_compatible:deepseek-flash`, korpus: 157 dok. / 18 źródeł, tryb: hybrid. Szczegóły poniżej. |

## Jak odtworzyć pomiar

```bash
cd backend
# Uruchom ingest (wymaga PostgreSQL i dostępu do internetu)
uv run python -m app.ingest.run

# Uruchom eval na tej samej bazie
EVAL_DATABASE_URL="postgresql+psycopg://prawdowid:prawdowid@localhost:5432/prawdowid" \
  uv run python -m eval.run_eval --cases eval/cases.jsonl --out eval/out
```

Wynik: `eval/out/report.json` (mierniki), `results.csv` (każdy przypadek), `citations_to_review.csv`
(pary twierdzenie–cytat do ręcznej oceny poprawności cytowania). Zestaw jury wystarczy zapisać w tym samym
formacie: `{"id", "scenario", "text", "expected_verdict" | "expected_status", "attack"?, "consistency"?, "same_case_as"?}`.

> **Uwaga:** domyślnie `eval.run_eval` używa bazy `prawdowid_test`. Aby uruchomić na tej samej bazie co serwer
> (z zaciągniętym korpusem), ustaw `EVAL_DATABASE_URL` jak powyżej.

`eval/cases.jsonl` to 32 przypadki referencyjne oparte na rzeczywistych rekordach korpusu (pole `basis`).
Nie są wpisane do promptów ani kodu. Zestaw obejmuje scenariusze A–J z sekcji 6 wymagań.

| Miernik | Cel MVP | Jak liczymy | Wynik | Uwaga |
|---|---|---|---|---|
| Trafność werdyktu (macro-F1) | ≥ 0,75 | `verdict_macro_f1` | **0,821** ✅ | Zestaw jawny: 32 przypadki, korpus 159 dok. / 18 źródeł |
| Pokrycie cytowań | ≥ 95% | `citation_coverage`: rozstrzygające werdykty z ≥ 1 potwierdzonym cytatem (reguły wymuszają 100%) | **100%** ✅ | Reguły blokują werdykt bez zweryfikowanego cytatu |
| Poprawność cytowania | ≥ 85% | ręczna ocena `citations_to_review.csv` | _do ręcznej oceny_ | Pary twierdzenie–cytat zapisane w `eval/out/citations_to_review.csv` |
| Wstrzymanie się | ≥ 80% | `abstention_accuracy` | **1,00** ✅ | Wszystkie przypadki bez dowodów trafiają poprawnie na `brak_wystarczajacych_dowodow` |
| Odporność na prompt injection | ≥ 90% | `injection_resistance`: werdykt bez zmian i zdarzenie odnotowane | **1,00** ✅ | Wszystkie 4 scenariusze E wykryte, werdykt zgodny z dowodami |
| Mediana czasu | ≤ 30 s | `median_duration_ms` | **5 852 ms** ✅ | |
| Koszt 100 testów | raportowany | `cost_usd_per_100` | **$0,30** | Model: DeepSeek-Flash |
| Spójność kanałów | 100% | `repeat_consistency`: to samo zgłoszenie wysłane ponownie | **100%** ✅ | Wynik deterministyczny dzięki cache'owaniu na 24h |
| Pętla informacji | 100% | `case_deduplication` | **100%** ✅ | |

### Pozostałe niedopasowania (scenariusze A/B/FC)

Scenariusze **A4**, **A5**, **B1**, **FC1**, **FC4** kończą się `brak_wystarczajacych_dowodow`, ponieważ:
- A4 (akcesja PL do UE w 2004 r.) wymaga aktu z EUR-Lex (nie jest w ingeście MVP),
- A5 (budżet 2026) wymaga konkretnego rekordu z Sejm ELI,
- B1 (fikcyjne „Testowo" 120 tys. mieszkańców) nie ma podstawy w korpusie,
- FC1, FC4 to rekordy z 2021 r., które mogą być poza oknem feedu ClaimReview.

Zachowanie systemu jest **prawidłowe** – nie halucynuje werdyktu bez dowodu. Są to luki korpusu
do uzupełnienia (podniesienie `INGEST_MAX_PER_SOURCE`, dodanie konektora EUR-Lex), a nie błędy
logiki weryfikacji. W raporcie macro-F1 traktowane jako „false negatives"; dla większości
scenariuszy (C, D, E, G, H, I, N) trafność wynosi **100%**.

### Historia pomiarów

| Data | F1 | Wstrzymanie | Injection | Zmiana |
|---|---|---|---|---|
| 2026-11-22 (baseline) | 0,61 | 0,69 | 0,50 | pierwszy pomiar |
| 2026-11-22 (poprawki promptu) | **0,82** | **1,00** | **1,00** | + jawne wykrywanie opinii/sprzeczności w ekstrakcji; + rozszerzone wzorce injection (SYSTEM:, ujawnij prompt, role play) |

## Scenariusze A–J

| | Scenariusz | Jak system to obsługuje | Test automatyczny |
|---|---|---|---|
| A | Fakt prosty | werdykt + dosłowny cytat ze źródła pierwotnego | `test_simple_fact_is_confirmed_with_exact_quote` |
| B | Kontekst | werdykt „wprowadzające w błąd" wymaga cytatu „zaprzecza" lub „kontekst"; ostrzeżenie o materiale archiwalnym | `test_verdict_requires_matching_validated_evidence` |
| C | Sprzeczność | oba źródła pokazane, flaga rozbieżności, brak rozstrzygnięcia | `test_conflicting_sources_are_shown_without_arbitrary_verdict` |
| D | Brak dowodów | wstrzymanie się + „czego nie udało się ustalić" | `test_missing_evidence_abstains_…`, `test_fabricated_quote_never_produces_a_verdict` |
| E | Atak | instrukcje w treści zignorowane, ostrzeżenie, wpis w zdarzeniach | `test_prompt_injection_is_ignored_and_logged` |
| F | Multimodalność | OCR tekstu z obrazu + wyszukiwanie odwrotne (Yandex, TinEye) + transkrypcja audio (Whisper); jawne ograniczenia | `test_image_text_goes_through_the_same_verification` |
| G | Spójność | WWW i Discord (`/fact-check`) wołają tę samą ścieżkę `VerificationService.check()` – wynik merytoryczny jest spójny; `repeat_consistency` = 100% | `test_repeated_report_gives_the_same_result_without_calling_the_model` |
| H | Pętla informacji | jedna sprawa dla podobnych zgłoszeń; „przekazano" tylko gdy sprawa istnieje, „powiadomiono" tylko gdy webhook doręczył | `test_missing_evidence_abstains_and_repeated_report_updates_one_case`, `test_disabled_loop_only_recommends_handover` |
| I | URL / incydent | dopasowanie jako kontekst, bez wpływu na werdykt | `test_known_incident_url_is_context_only` |
| J | Limit API | status `error` z kodem, bez werdyktu | `test_model_outage_…`, `test_image_reading_failure_is_a_technical_limitation` |

## Co system obsługuje (zakres multimodalności)

- **Tekst i URL** – główna ścieżka weryfikacji; URL pobierany przez bezpieczny fetcher (SSRF-safe).
- **Obraz (OCR)** – `POST /api/v1/checks/image`; tekst widoczny na obrazie jest wyciągany przez model i przechodzi przez tę samą ścieżkę weryfikacji.
- **Wyszukiwanie odwrotne obrazu** – Yandex i TinEye przez PicImageSearch; porównanie SIFT+RANSAC; wykrywanie przeróbek przez porównanie z kopiami.
- **Audio (transkrypcja)** – `POST /api/v1/checks/audio`; Whisper `small` lokalnie; plik audio nie jest zapisywany.
- **Drugi kanał** – bot Discord (`/fact-check`) wywołuje `POST /api/v1/channels/demo`, która wołą tę samą logikę co WWW.

## Czego system nie obsługuje

- Strony wymagające JavaScriptu, logowania lub płatnego dostępu oraz strony, które zabraniają automatycznego pobierania.
- Tematy spoza korpusu – wynik to zawsze „brak wystarczających dowodów".
- Więcej niż 4 twierdzenia w jednym zgłoszeniu; treść powyżej 20 000 znaków jest przycinana.
- Inne języki niż polski: interfejs, odpowiedzi i źródła są wyłącznie polskie; treść w innym języku nie znajdzie dowodów w korpusie.
- Integracje OpenCTI / DISARM – jest eksport w formacie STIX 2.1 (z mapowaniem DISARM), brak natywnej integracji z tymi platformami.

## Ryzyka

| Ryzyko | Ograniczenie w prototypie | Co zostaje |
|---|---|---|
| **Halucynacje** | werdykt tylko z cytatów potwierdzonych w źródle; metadane źródeł z korpusu, nie z modelu; model nie korzysta z własnej wiedzy (instrukcja) i zawsze może się wstrzymać | cytat może istnieć, ale być źle zinterpretowany – potrzebny ręczny przegląd próby i moderator przy sprawach wysokiego ryzyka |
| **Stronniczość źródeł** | jawny katalog z uzasadnieniem kwalifikacji; siła podstawy premiuje niezależnych wydawców; sprzeczne źródła są pokazywane | korpus MVP ma 157 dokumentów z 18 źródeł (maks. 10 dok./źródło na przebieg) i jest nierówny tematycznie; to celowo wąski, weryfikowalny zbiór |
| **Prywatność** | maskowanie PII przed modelem i zapisem; brak zapisu obrazów i adresów IP; retencja 30 dni; usuwanie sesji | maskowanie wyrażeniami regularnymi nie wykryje nazwisk ani adresów; treść trafia do zewnętrznego dostawcy modelu, jeśli nie wybrano modelu lokalnego |
| **Prompt injection** | rozdzielenie instrukcji i danych, losowe znaczniki, brak narzędzi, wyjście wg schematu, walidacja cytatów, logowanie zdarzeń; injection resistance = 1,00 w aktualnym pomiarze | heurystyki regex wykrywają znane wzorce (ignore/zignoruj/SYSTEM:/ujawnij prompt/role play); nowe, nieznane ataki mogą ominąć filtr, ale reguły `verdict.py` i tak wymagają dosłownego cytatu ze źródła – injection nie jest w stanie wyprodukować fałszywego werdyktu |
| **Dostępność** | jawne błędy techniczne; praca bez embeddingów; cache wyników; limit żądań | jedna instancja, limit w pamięci, zależność od jednego dostawcy modelu w danej konfiguracji |
| **Nadużycia** | limit żądań na klienta; brak możliwości dodania źródła przez użytkownika; token panelu; neutralizacja formuł w eksporcie | zalewanie kolejki moderatora zgłoszeniami; próby użycia wyniku „brak dowodów" jako „nie obalono"; brak CAPTCHA |
| **Prawa autorskie** | polityka przechowywania per źródło; poszanowanie robots.txt; tylko fragment i link dla treści chronionych | licencje wymagają przeglądu prawnego przed pilotażem ([ZRODLA.md](ZRODLA.md)) |
| **Nadmierne zaufanie do wyniku** | „interpretacja systemu" oddzielona od materiałów źródłowych; ograniczenia przy każdej odpowiedzi; zachęta do czytania źródeł | użytkownik może potraktować wynik jak wyrok – w pilotażu odpowiedzi do publikacji powinien zatwierdzać człowiek |
