# Testy, ograniczenia i ryzyka

## Stan pomiarów

| Co | Stan |
|---|---|
| Testy automatyczne (`uv run pytest`) | **59/59 przechodzi.** Model jest w nich podstawiony, więc sprawdzają logikę, reguły, bezpieczeństwo i kanały – nie jakość modelu. |
| Żądania do dostawców modelu | Kształt żądań (API zgodne z OpenAI, w tym tryb `json_object` używany przez DeepSeek, oraz Anthropic) oraz obsługa odmowy, uciętej odpowiedzi, limitu i błędów są sprawdzone na atrapie transportu HTTP – **nie na prawdziwym API**. |
| Wyszukiwanie na prawdziwym korpusie | Sprawdzone ręcznie: zapytania po polsku znajdują właściwe dokumenty, także anglojęzyczne; pytanie spoza korpusu zwraca 0 wyników. |
| Ścieżka bez klucza API (scenariusz J) | Sprawdzona na działającym serwerze: status `error`, brak werdyktu, lista materiałów. |
| **Mierniki z sekcji 6 na prawdziwym modelu** | **Jeszcze niezmierzone** – środowisko, w którym powstał kod, nie miało klucza API. Tabelę poniżej trzeba uzupełnić po uruchomieniu `eval.run_eval`. |

## Jak odtworzyć pomiar

```bash
cd backend
uv run python -m eval.run_eval --cases eval/cases.jsonl --out eval/out
```

Wynik: `eval/out/report.json` (mierniki), `results.csv` (każdy przypadek), `citations_to_review.csv`
(pary twierdzenie–cytat do ręcznej oceny poprawności cytowania). Zestaw jury wystarczy zapisać w tym samym
formacie: `{"id", "scenario", "text", "expected_verdict" | "expected_status", "attack"?, "consistency"?, "same_case_as"?}`.

`eval/cases.jsonl` to 15 przypadków startowych opartych na rzeczywistych rekordach korpusu (pole `basis`).
Nie są wpisane do promptów ani kodu. Przed oceną warto rozszerzyć zestaw do co najmniej 30 przypadków.

| Miernik | Cel MVP | Jak liczymy | Wynik |
|---|---|---|---|
| Trafność werdyktu (macro-F1) | ≥ 0,75 | `verdict_macro_f1` | _do zmierzenia_ |
| Pokrycie cytowań | ≥ 95% | `citation_coverage`: rozstrzygające werdykty z ≥ 1 potwierdzonym cytatem (reguły wymuszają 100%) | _do zmierzenia_ |
| Poprawność cytowania | ≥ 85% | ręczna ocena `citations_to_review.csv` | _do zmierzenia_ |
| Wstrzymanie się | ≥ 80% | `abstention_accuracy` | _do zmierzenia_ |
| Odporność na prompt injection | ≥ 90% | `injection_resistance`: werdykt bez zmian i zdarzenie odnotowane | _do zmierzenia_ |
| Mediana czasu | ≤ 30 s | `median_duration_ms` | _do zmierzenia_ |
| Koszt 100 testów | raportowany | `cost_usd_per_100` | _do zmierzenia_ |
| Spójność kanałów | 100% | nie dotyczy – działa tylko kanał WWW; mierzymy `repeat_consistency`: to samo zgłoszenie wysłane ponownie daje ten sam werdykt i te same źródła | _do zmierzenia_ |
| Pętla informacji | 100% | `case_deduplication` | _do zmierzenia_ |

## Scenariusze A–J

| | Scenariusz | Jak system to obsługuje | Test automatyczny |
|---|---|---|---|
| A | Fakt prosty | werdykt + dosłowny cytat ze źródła pierwotnego | `test_simple_fact_is_confirmed_with_exact_quote` |
| B | Kontekst | werdykt „wprowadzające w błąd” wymaga cytatu „zaprzecza” lub „kontekst”; ostrzeżenie o materiale archiwalnym | `test_verdict_requires_matching_validated_evidence` |
| C | Sprzeczność | oba źródła pokazane, flaga rozbieżności, brak rozstrzygnięcia | `test_conflicting_sources_are_shown_without_arbitrary_verdict` |
| D | Brak dowodów | wstrzymanie się + „czego nie udało się ustalić” | `test_missing_evidence_abstains_…`, `test_fabricated_quote_never_produces_a_verdict` |
| E | Atak | instrukcje w treści zignorowane, ostrzeżenie, wpis w zdarzeniach | `test_prompt_injection_is_ignored_and_logged` |
| F | Multimodalność | odczyt tekstu i dat z obrazu, metadane EXIF, jawne ograniczenia | `test_image_text_goes_through_the_same_verification` |
| G | Spójność | **brak drugiego kanału** – nie da się wykonać; ta sama treść wysłana ponownie daje ten sam wynik | `test_repeated_report_gives_the_same_result_without_calling_the_model` |
| H | Pętla informacji | jedna sprawa dla podobnych zgłoszeń; „przekazano” tylko gdy sprawa istnieje, „powiadomiono” tylko gdy webhook doręczył | `test_missing_evidence_abstains_and_repeated_report_updates_one_case`, `test_disabled_loop_only_recommends_handover` |
| I | URL / incydent | dopasowanie jako kontekst, bez wpływu na werdykt | `test_known_incident_url_is_context_only` |
| J | Limit API | status `error` z kodem, bez werdyktu | `test_model_outage_…`, `test_image_reading_failure_is_a_technical_limitation` |

## Czego system nie obsługuje

- Dźwięk i wideo (brak transkrypcji).
- Wyszukiwanie odwrotne obrazu, wykrywanie przeróbek i deepfake'ów – obraz służy wyłącznie do odczytu tekstu.
- Strony wymagające JavaScriptu, logowania lub płatnego dostępu oraz strony, które zabraniają automatycznego pobierania.
- **Drugi kanał komunikacji** (SMS, komunikator itp.) ani adapter demonstracyjny – działa tylko interfejs WWW. To wymaganie podstawowe konkursu.
- Tematy spoza korpusu – wynik to zawsze „brak wystarczających dowodów”.
- Więcej niż 4 twierdzenia w jednym zgłoszeniu; treść powyżej 20 000 znaków jest przycinana.
- Interfejs i odpowiedzi tylko po polsku (źródła mogą być w innych językach).
- Integracje OpenCTI / DISARM – jest tylko eksport CSV/JSON.

## Ryzyka

| Ryzyko | Ograniczenie w prototypie | Co zostaje |
|---|---|---|
| **Halucynacje** | werdykt tylko z cytatów potwierdzonych w źródle; metadane źródeł z korpusu, nie z modelu; model nie korzysta z własnej wiedzy (instrukcja) i zawsze może się wstrzymać | cytat może istnieć, ale być źle zinterpretowany – potrzebny ręczny przegląd próby i moderator przy sprawach wysokiego ryzyka |
| **Stronniczość źródeł** | jawny katalog z uzasadnieniem kwalifikacji; siła podstawy premiuje niezależnych wydawców; sprzeczne źródła są pokazywane | korpus demonstracyjny jest mały i nierówny tematycznie (dużo fact-checkingu z USA); oceny redakcji fact-checkingowych przyjmujemy jako dowód poziomu 2 |
| **Prywatność** | maskowanie PII przed modelem i zapisem; brak zapisu obrazów i adresów IP; retencja 30 dni; usuwanie sesji | maskowanie wyrażeniami regularnymi nie wykryje nazwisk ani adresów; treść trafia do zewnętrznego dostawcy modelu, jeśli nie wybrano modelu lokalnego |
| **Prompt injection** | rozdzielenie instrukcji i danych, losowe znaczniki, brak narzędzi, wyjście wg schematu, walidacja cytatów, logowanie zdarzeń | heurystyki nie wykryją każdego ataku; atak może skłonić model do wstrzymania się (obniżenie użyteczności, nie fałszywy werdykt) |
| **Dostępność** | jawne błędy techniczne; praca bez embeddingów; pamięć wyników; limit żądań | jedna instancja, limit w pamięci, zależność od jednego dostawcy modelu w danej konfiguracji |
| **Nadużycia** | limit żądań na klienta; brak możliwości dodania źródła przez użytkownika; token panelu; neutralizacja formuł w eksporcie | zalewanie kolejki moderatora zgłoszeniami; próby użycia wyniku „brak dowodów” jako „nie obalono”; brak CAPTCHA |
| **Prawa autorskie** | polityka przechowywania per źródło; poszanowanie robots.txt; tylko fragment i link dla treści chronionych | licencje wymagają przeglądu prawnego przed pilotażem ([ZRODLA.md](ZRODLA.md)) |
| **Nadmierne zaufanie do wyniku** | „interpretacja systemu” oddzielona od materiałów źródłowych; ograniczenia przy każdej odpowiedzi; zachęta do czytania źródeł | użytkownik może potraktować wynik jak wyrok – w pilotażu odpowiedzi do publikacji powinien zatwierdzać człowiek |
