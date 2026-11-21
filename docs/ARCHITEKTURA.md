# Architektura

## Przepływ jednego zgłoszenia

```
kanał (obecnie WWW)
  → Submission(tekst | URL | obraz)
  → 1. przygotowanie wejścia   walidacja, pobranie strony (ochrona SSRF, robots.txt) lub odczyt obrazu,
                               maskowanie danych osobowych, wykrycie prób prompt injection
  → 2. kontekst                dopasowanie URL/domeny do katalogu incydentów, status źródła (neutralne ostrzeżenia)
  → 3. pamięć wyników          ta sama treść + ten sam korpus + ten sam model → ten sam wynik (spójność kanałów)
  → 4. wydzielenie twierdzeń   MODEL: twierdzenia, rodzaj (fakt/opinia/prognoza), zapytania, ryzyko
  → 5. wyszukiwanie            KOD: pgvector (kosinus) + rerank hybrydowy (similarity + pokrycie keywordów)
  → 6. ocena dowodów           MODEL: dla każdego fragmentu stanowisko + DOSŁOWNY cytat, propozycja werdyktu
  → 7. reguły werdyktu         KOD: weryfikacja cytatów, werdykt, siła podstawy, sprzeczności
  → 8. pętla informacji        KOD: sprawa moderatora dla nierozstrzygniętych, grupowanie, powiadomienie
  → CheckResponse → zapis przebiegu → odpowiedź w formie właściwej dla kanału
```

Kanał zna tylko `VerificationService.check()` i model `CheckResponse`. Obecnie jedynym kanałem jest WWW.
Kolejny kanał to jeden router, który zamienia wiadomość na `Submission` i przedstawia wynik w swojej formie –
logika weryfikacji się nie zmienia.

## Dlaczego werdykt nie jest „etykietą modelu”

Model językowy rozumie pytanie, porównuje materiały i formułuje uzasadnienie – ale nie decyduje sam.

1. Model nie ma żadnych narzędzi i odpowiada wyłącznie danymi zgodnymi ze schematem.
2. Dla każdego fragmentu źródła musi podać dosłowny cytat. `core/verdict.py` sprawdza, czy cytat naprawdę
   występuje w tym fragmencie. Niepotwierdzone cytaty są odrzucane.
3. Werdykt wynika z potwierdzonych cytatów:

| Propozycja modelu | Warunek | Wynik |
|---|---|---|
| potwierdzone | ≥ 1 potwierdzony cytat „potwierdza”, brak „zaprzecza” | potwierdzone |
| fałszywe | ≥ 1 potwierdzony cytat „zaprzecza”, brak „potwierdza” | fałszywe |
| wprowadzające w błąd | ≥ 1 potwierdzony cytat „zaprzecza” lub „kontekst” | wprowadzające w błąd |
| dowolna | cytat pochodzi z mediów (poziom 3) | cytat liczy się tylko jako „kontekst” |
| potwierdzone / fałszywe | są cytaty „potwierdza” **i** „zaprzecza” | brak wystarczających dowodów + jawna rozbieżność |
| dowolna rozstrzygająca | brak wymaganego cytatu | brak wystarczających dowodów |
| brak dowodów / nie podlega weryfikacji | – | bez zmian (model zawsze może się wstrzymać) |

4. Linki, tytuły, wydawcy i daty pochodzą z rekordu korpusu, nigdy z tekstu wygenerowanego przez model –
   system nie może więc „wymyślić” źródła.
5. Gdy reguły korygują propozycję modelu, uzasadnienie modelu jest zastępowane stałym komunikatem.

**Siła podstawy** to suma jawnych przesłanek (każda jest pokazywana użytkownikowi):
jakość najlepszego źródła (pierwotne/urzędowe 0,35; fact-checking 0,28; media 0,12),
liczba niezależnych wydawców (0,10 / 0,20 / 0,30), aktualność (0,20 → 0,05 dla materiału archiwalnego),
zgodność źródeł (+0,15 / −0,15). Progi: mocna ≥ 0,75, umiarkowana ≥ 0,5, poniżej słaba.

## Modele i dostawcy

| Element | Domyślnie | Wymiana |
|---|---|---|
| Model językowy | DeepSeek `deepseek-flash` (obecnie DeepSeek-V4.1-Flash) przez API zgodne z OpenAI; odpowiedź w trybie `json_object`, walidowana schematem z jedną ponowną próbą | `LLM_BASE_URL` + `LLM_MODEL` – Mistral (UE), Ollama/vLLM (własny serwer, np. Bielik), OpenRouter; `LLM_PROVIDER=anthropic` – Claude |
| Embeddingi | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384) przez fastembed (ONNX), **lokalnie** | `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `EMBEDDING_BACKEND=none` |
| Wyszukiwanie | PostgreSQL + pgvector (HNSW, cosine), top 20 kandydatów, rerank 0.8×similarity + 0.2×keyword overlap | `RETRIEVAL_*` w konfiguracji |
| Baza | PostgreSQL + pgvector (`pgvector/pgvector:pg17`) | `DATABASE_URL` (SQLAlchemy + psycopg) |
| Odczyt obrazu | ten sam model językowy (wizja) | idzie za `LLM_PROVIDER` |

**Miejsce przetwarzania.** Wyszukiwanie, embeddingi, baza i korpus działają na serwerze usługi. Do dostawcy
modelu trafia treść zgłoszenia po zamaskowaniu danych osobowych oraz fragmenty źródeł. Domyślny dostawca
(DeepSeek) ma siedzibę w Chinach, czyli poza EOG; jego dokumentacja API nie podaje miejsca przetwarzania danych.
Przełączenie na dostawcę z EOG lub model lokalny to zmiana dwóch zmiennych środowiskowych, bez zmian w kodzie. Opis miejsca przetwarzania (`PROCESSING_LOCATION`) jest pokazywany użytkownikowi.

**Zachowanie przy awarii.** Brak klucza, limit, odmowa lub awaria modelu → status `error` z kodem
(`llm_not_configured`, `llm_unavailable`, `llm_rate_limited`, `llm_refused`, `llm_bad_output`, `ocr_unavailable`,
`url_*`, `image_*`) i komunikatem „to problem techniczny, a nie wynik sprawdzenia”. Brak modelu embeddingów →
materiały podobne są pomijane, a odpowiedź zawiera jawne ostrzeżenie (werdykt nadal powstaje na fact-checkach).

## Bezpieczeństwo

- **Prompt injection.** Instrukcje są tylko w roli `system`. Treść użytkownika, pobrana strona, tekst z obrazu
  i fragmenty źródeł trafiają do wiadomości jako dane w blokach o losowej nazwie znacznika (treść nie może
  „zamknąć” bloku). Znaki niewidoczne są usuwane. Heurystyki (polskie i angielskie wzorce ataków) oraz flaga zwracana przez model powodują
  ostrzeżenie dla użytkownika i wpis w `security_events`. Nawet skuteczne przekonanie modelu nie wystarczy:
  werdykt wymaga cytatu obecnego w źródle z korpusu.
- **Pobieranie URL.** Tylko http/https i porty 80/443; adres jest rozwiązywany i odrzucany, jeśli którykolwiek
  rekord wskazuje sieć prywatną; połączenie idzie pod zweryfikowany adres IP (ochrona przed DNS rebinding);
  przekierowania są walidowane od nowa; limit rozmiaru i czasu; tylko HTML/tekst; respektowane robots.txt.
  Strona podana przez użytkownika jest **materiałem do sprawdzenia, nigdy dowodem**.
- **Wejście.** Walidacja Pydantic, limity długości, limit rozmiaru i typu obrazu, limit żądań na klienta.
- **Sekrety.** Tylko zmienne środowiskowe / `.env` (w `.gitignore`); panel moderatora wymaga `ADMIN_TOKEN`
  (bez niego jest wyłączony).
- **Eksport.** CSV neutralizuje formuły arkusza (CSV injection).

## Prywatność

- Maskowanie e-maili, telefonów, numerów PESEL (z sumą kontrolną), kont i kart **przed** wysłaniem do modelu i zapisem.
- Obrazów nie zapisujemy; przed wysłaniem do modelu usuwamy EXIF (w tym GPS).
- Adresy IP służą tylko do limitu żądań w pamięci (w postaci skrótu z solą) i nie są zapisywane.
- Dla linków zapisujemy tylko początek pobranej treści.
- Wynik jest dostępny pod losowym, niezgadywalnym adresem (`/sprawdzenie/{id}`) – każdy, kto zna link, może go otworzyć.
- Retencja: `RETENTION_DAYS` (domyślnie 30), czyszczenie co godzinę. `DELETE /api/v1/sessions/{id}` usuwa dane sesji.

## Obserwowalność

Każde sprawdzenie zapisuje: pytanie (po maskowaniu), czas, kanał, wykorzystane źródła, wynik, czasy etapów,
liczbę wywołań i tokenów, szacunkowy koszt, kod błędu. Log JSON na sprawdzenie zawiera dodatkowo liczbę
odrzuconych cytatów. `GET /api/v1/admin/metrics`: odsetek wstrzymań, mediana i p95 czasu, koszt na 1000 zapytań,
błędy według kodów, zdarzenia bezpieczeństwa.

## Koszty i skalowanie (szacunek – do potwierdzenia pomiarem `eval.run_eval`)

Jedno zgłoszenie to 1 wywołanie modelu na wydzielenie twierdzeń + 1 na każde twierdzenie typu „fakt”
(równolegle). Przy założeniu ok. 2 twierdzeń, 8 tys. tokenów wejścia i 3 tys. tokenów wyjścia (z rozumowaniem):

| Model | Cennik (USD / 1 mln tokenów) | ~ koszt 1 000 zgłoszeń |
|---|---|---|
| `deepseek-flash` (domyślny) | 0,30 / 1,20 w godzinach szczytu, połowa poza nimi | ok. 3–6 USD |
| `claude-opus-5-5` | 4 / 20 | ok. 90 USD |
| model lokalny (Ollama/vLLM) | – | koszt własnego serwera |

To założenia, nie pomiar: faktyczne zużycie tokenów podaje `meta` każdej odpowiedzi i raport ewaluacji.
Powtórzone zgłoszenia (24 h) są obsługiwane z pamięci wyników bez kosztu modelu.

Większy ruch: wąskim gardłem jest model. Usługa jest bezstanowa poza bazą – można uruchomić wiele instancji
po przeniesieniu limitu żądań do Redis i bazy do Postgresa. Indeks (kilkaset fragmentów) odpowiada w ~20 ms.

## Najważniejsze ograniczenia

- Usługa działa wyłącznie po polsku: interfejs, odpowiedzi, zapytania do wyszukiwarki i wszystkie źródła.
- Odpowiedź jest tak dobra, jak korpus: poza jego zakresem system zawsze się wstrzymuje.
- Jakość ocen zależy od modelu; reguły gwarantują istnienie cytatu, a nie to, że cytat został dobrze zrozumiany.
  Poprawność cytowań trzeba mierzyć przeglądem ludzkim (`eval/out/citations_to_review.csv`).
- Limit 4 twierdzeń i 20 000 znaków na zgłoszenie.
- Limit żądań i blokada grupowania spraw działają w pamięci jednego procesu.
- Pełna lista nieobsługiwanych przypadków: [TESTY-I-RYZYKA.md](TESTY-I-RYZYKA.md).
