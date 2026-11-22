# Architektura

## Przepływ jednego zgłoszenia

```
kanał (WWW lub Discord)
  → Submission(tekst | URL | obraz | nagranie)
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

  równolegle z krokami 5–7 (warstwa wspierająca, nigdy rozstrzygająca):
  → słowa kluczowe             BIELIK (lokalnie, Ollama/vLLM): słowa kluczowe i główny temat;
                               przy awarii model zdalny, a potem zapytania z kroku 4
  → fact-checki zewnętrzne     KOD: Google Fact Check Tools dla słów kluczowych
  → podsumowanie całości       MODEL: jeden werdykt dla całego materiału, uzgodniony z ocenami twierdzeń
```

Kanał zna tylko `VerificationService.check()` i model `CheckResponse`. Działające kanały:
- **WWW** (Next.js, `frontend/`) – formularz + wysyłka do `POST /api/v1/checks`, `…/checks/image`, `…/checks/audio`.
- **Discord** (`discord-bot/`) – komenda `/fact-check` (opcje `tekst` / `url` / `zdjecie`) woła dokładnie te same
  endpointy backendu, więc werdykt dla tego samego zgłoszenia jest spójny.
- **Demo adapter** (`POST /api/v1/channels/demo`) – minimalny adapter do testów scenariusza G (spójność kanałów).

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

## Dwie warstwy odpowiedzi

| Warstwa | Pola `CheckResponse` | Skąd się bierze | Rola |
|---|---|---|---|
| dowodowa | `claims[]` (`evidence`, `strength`, `conflict`, `missing`) | katalog źródeł + cytaty sprawdzone w `core/verdict.py` | **rozstrzygająca** |
| wspierająca | `verdict`, `confidence`, `justification`, `keywords`, `main_topic`, `fact_check_results[]` | lokalny model słów kluczowych, Google Fact Check Tools, podsumowanie modelu | kontekst i streszczenie |

Warstwa wspierająca nigdy nie nadpisuje ocen twierdzeń. `_reconcile()` w `core/pipeline.py` pilnuje,
by podsumowanie nie było mocniejsze niż dowody: jeśli żadne twierdzenie nie zostało rozstrzygnięte,
podsumowanie też nie rozstrzyga. Awaria słów kluczowych, Google Fact Check albo podsumowania
zostawia oceny twierdzeń nietknięte i daje tylko ostrzeżenie.

**Siła podstawy** to suma jawnych przesłanek (każda jest pokazywana użytkownikowi):
jakość najlepszego źródła (pierwotne/urzędowe 0,35; fact-checking 0,28; media 0,12),
liczba niezależnych wydawców (0,10 / 0,20 / 0,30), aktualność (0,20 → 0,05 dla materiału archiwalnego),
zgodność źródeł (+0,15 / −0,15). Progi: mocna ≥ 0,75, umiarkowana ≥ 0,5, poniżej słaba.

## Modele i dostawcy

| Element | Domyślnie | Wymiana |
|---|---|---|
| Model językowy | DeepSeek `deepseek-flash` (obecnie DeepSeek-V4.1-Flash) przez API zgodne z OpenAI; odpowiedź w trybie `json_object`, walidowana schematem z jedną ponowną próbą | `LLM_BASE_URL` + `LLM_MODEL` – Mistral (UE), Ollama/vLLM (własny serwer, np. Bielik), OpenRouter; `LLM_PROVIDER=anthropic` – Claude |
| Embeddingi | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384) przez fastembed (ONNX), **lokalnie** | `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `EMBEDDING_BACKEND=none` |
| Wyszukiwanie | PostgreSQL + pgvector (HNSW, cosine), kandydaci + rerank; fallback leksykalny, gdy brak embeddingów | `RETRIEVAL_*` w konfiguracji |
| Baza | PostgreSQL + pgvector (`pgvector/pgvector:pg17`) — jedyne źródło prawdy | `DATABASE_URL` (SQLAlchemy + psycopg) |
| Słowa kluczowe | **Bielik 4.5B v3.0 Instruct** (`SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0`) przez Ollamę/vLLM, **lokalnie** | `BIELIK_BASE_URL` + `BIELIK_MODEL`; puste `BIELIK_BASE_URL` wyłącza etap |
| Fact-checki zewnętrzne | Google Fact Check Tools | `GOOGLE_FACTCHECK_API_KEY`; bez klucza etap jest pomijany |
| Transkrypcja nagrań | faster-whisper (`small`, CPU/int8), **lokalnie**; dźwięk nie jest zapisywany | `WHISPER_*`, `AUDIO_MAX_*` |
| Odczyt obrazu | ten sam model językowy (wizja) | idzie za `LLM_PROVIDER` |

**Miejsce przetwarzania.** Wyszukiwanie, embeddingi, baza i korpus działają na serwerze usługi. Do dostawcy
modelu trafia treść zgłoszenia po zamaskowaniu danych osobowych oraz fragmenty źródeł. Domyślny dostawca
(DeepSeek) ma siedzibę w Chinach, czyli poza EOG; jego dokumentacja API nie podaje miejsca przetwarzania danych.
Przełączenie na dostawcę z EOG lub model lokalny to zmiana dwóch zmiennych środowiskowych, bez zmian w kodzie. Opis miejsca przetwarzania (`PROCESSING_LOCATION`) jest pokazywany użytkownikowi.

**Zachowanie przy awarii.** Brak klucza, limit, odmowa lub awaria modelu → status `error` z kodem
(`llm_not_configured`, `llm_unavailable`, `llm_rate_limited`, `llm_refused`, `llm_bad_output`, `ocr_unavailable`,
`transcription_unavailable`, `url_*`, `image_*`, `audio_*`) i komunikatem „to problem techniczny, a nie wynik
sprawdzenia”. Brak modelu embeddingów → wyszukiwanie przechodzi w jawny tryb leksykalny z ostrzeżeniem
`retrieval_degraded`; werdykt nadal wymaga cytatu z korpusu.

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
- Wynik jest dostępny pod losowym, niezgadywalnym adresem (`/analiza/{id}`) – każdy, kto zna link, może go otworzyć.
- Retencja: `RETENTION_DAYS` (domyślnie 30), czyszczenie co godzinę. `DELETE /api/v1/sessions/{id}` usuwa dane sesji.

## Obserwowalność

Każde sprawdzenie zapisuje: pytanie (po maskowaniu), czas, kanał, wykorzystane źródła, wynik, czasy etapów,
liczbę wywołań i tokenów, szacunkowy koszt, kod błędu. Log JSON na sprawdzenie zawiera dodatkowo liczbę
odrzuconych cytatów. `GET /api/v1/admin/metrics`: odsetek wstrzymań, mediana i p95 czasu, koszt na 1000 zapytań,
błędy według kodów, zdarzenia bezpieczeństwa.

## Koszty i skalowanie

Jedno zgłoszenie to 1 wywołanie modelu na wydzielenie twierdzeń + 1 na każde twierdzenie typu „fakt"
(równolegle). **Pomiar `eval.run_eval` (2026-11-22, 32 przypadki, DeepSeek-Flash poza szczytem):
$0,096 łącznie, czyli $0,30 za 100 zapytań, czyli ok. $3 za 1 000 zapytań.**

| Model | Cennik (USD / 1 mln tokenów) | ~ koszt 1 000 zgłoszeń |
|---|---|---|
| **`deepseek-flash` (domyślny, zmierzone)** | 0,30 / 1,20 w godzinach szczytu, połowa poza nimi | **ok. 3 USD poza szczytem, 6 USD w szczycie** |
| `gpt-5.2-mini` / `gemini-3-flash` (alternatywy z katalogu) | 0,25 / 2,00 i 0,30 / 2,50 | ok. 8–10 USD |
| model lokalny (Ollama/vLLM, np. Bielik) | – | koszt własnego serwera |

Faktyczne zużycie tokenów podaje `meta` każdej odpowiedzi i raport `eval/out/report.json`.
Pełny kosztorys (usługi zewnętrzne, infrastruktura, kanały, skalowanie): [KOSZTY.md](KOSZTY.md).
Powtórzone zgłoszenia (24 h) są obsługiwane z pamięci wyników bez kosztu modelu.

Większy ruch: wąskim gardłem jest model (DeepSeek w API i lokalny Bielik na CPU). Usługa jest bezstanowa poza
bazą, a baza to już PostgreSQL, więc można uruchomić wiele instancji backendu korzystających z jednej bazy.
Wcześniej trzeba przenieść do Redis limit żądań i blokadę grupowania spraw, które dziś działają w pamięci procesu. Indeks (kilkaset fragmentów) odpowiada w ~20 ms.

## Najważniejsze ograniczenia

- Usługa działa wyłącznie po polsku: interfejs, odpowiedzi, zapytania do wyszukiwarki i wszystkie źródła.
- Odpowiedź jest tak dobra, jak korpus: poza jego zakresem system zawsze się wstrzymuje.
- Jakość ocen zależy od modelu; reguły gwarantują istnienie cytatu, a nie to, że cytat został dobrze zrozumiany.
  Poprawność cytowań trzeba mierzyć przeglądem ludzkim (`eval/out/citations_to_review.csv`).
- Limit 4 twierdzeń i 20 000 znaków na zgłoszenie.
- Limit żądań i blokada grupowania spraw działają w pamięci jednego procesu.
- Pełna lista nieobsługiwanych przypadków: [TESTY-I-RYZYKA.md](TESTY-I-RYZYKA.md).

## Sesja i zgoda na politykę prywatności

Numer sesji (`prawdowid_session`) i wersja zaakceptowanej polityki (`prawdowid_privacy_consent`)
są trzymane w ciasteczkach, nie w `localStorage`, dzięki czemu backend widzi je przy każdym żądaniu.
Ciasteczka ustawia JavaScript (nie są HttpOnly, bo frontend musi je czytać), mają `SameSite=Lax`
i `Secure` po HTTPS; przy wdrożeniu frontendu i backendu na osobne domeny trzeba zmienić
na `SameSite=None; Secure`. CORS ma `allow_credentials=True` przy jawnej liście origins.

`POST /api/v1/checks` bierze numer sesji z treści żądania, a gdy go nie ma – z ciasteczka.
Treść ciasteczka pochodzi od klienta, więc jej format jest sprawdzany przed użyciem
(`session_from_cookie` w `api/deps.py`).

Tabela `privacy_consents` przechowuje **wyłącznie** numer sesji, wersję polityki, fakt zgody
i czas zapisu – bez treści sprawdzeń i bez odpowiedzi modelu (te są w tabeli `checks`).
Usunięcie sesji (`DELETE /api/v1/sessions/{id}`) kasuje też zgodę.
