# Koszty

Dla obywatela usługa jest **bezpłatna** we wszystkich kanałach (WWW i Discord). Nie ma kanału z opłatami
operatora, takimi jak SMS. Koszty ponosi wyłącznie operator usługi: płaci za model językowy w API
i za jeden serwer.

> **Stan:** liczby poniżej to szacunek oparty na cennikach dostawców (stan na 2026-11) i założonym zużyciu
> tokenów. Wartości zmierzone trzeba wpisać w sekcji 7 po uruchomieniu `eval.run_eval`.

## W skrócie

| Pozycja | Koszt |
|---|---|
| 1 sprawdzenie (DeepSeek V4.1 Flash) | ok. 0,003–0,006 USD |
| **1 000 zapytań** | **ok. 3–6 USD** |
| 100 testów referencyjnych | ok. 0,30–0,60 USD |
| Kanał Discord | 0 USD (bot działa na tym samym serwerze co backend) |
| Model lokalny Bielik, embeddingi, Whisper, wyszukiwanie | 0 USD (działają na naszym serwerze) |
| Google Fact Check Tools, odwrotne wyszukiwanie obrazu | 0 USD (zob. ograniczenia w sekcji 3) |
| Serwer (wszystkie komponenty) | stała opłata miesięczna, zob. sekcja 4 |

## 1. Z czego składa się koszt jednego sprawdzenia

Płatne jest tylko wywołanie modelu językowego w API (domyślnie DeepSeek, `deepseek-flash`). Pozostałe
kroki działają lokalnie albo korzystają z bezpłatnych usług.

| Krok | Gdzie działa | Płatny? |
|---|---|---|
| Odczyt tekstu ze zrzutu ekranu (OCR), tylko dla obrazów | DeepSeek (API) | tak, 1 wywołanie |
| Wydzielenie twierdzeń i decyzja, czy dopytać użytkownika | DeepSeek (API) | tak, 1 wywołanie |
| Każda runda doprecyzowania (maks. `CLARIFICATION_MAX_ROUNDS=2`) | DeepSeek (API) | tak, wydzielenie twierdzeń powtarza się |
| Ocena dowodów dla każdego twierdzenia (maks. 4, równolegle) | DeepSeek (API) | tak, 1 wywołanie na twierdzenie |
| Wstępne sprawdzenie i słowa kluczowe | Bielik 4.5B, lokalnie (Ollama) | nie |
| Wyszukiwanie w korpusie (BM25 + embeddingi, PostgreSQL + pgvector) | lokalnie | nie |
| Transkrypcja nagrania | Whisper `small`, lokalnie (CPU) | nie |
| Fact-checki jako kontekst wspierający | Google Fact Check Tools API | nie |
| Odwrotne wyszukiwanie i porównanie obrazu | Yandex i TinEye (bez klucza API) + porównanie lokalne | nie |

**Założenie:** typowe zgłoszenie z tekstem lub linkiem ma ok. 2 twierdzenia, czyli 3 wywołania modelu,
łącznie ok. 8 tys. tokenów wejścia i 3 tys. tokenów wyjścia (z rozumowaniem).

```
8 000 × 0,30 USD / 1 mln + 3 000 × 1,20 USD / 1 mln = 0,0024 + 0,0036 = 0,006 USD
```

DeepSeek podaje stawki dla godzin szczytu, a poza szczytem pobiera połowę. Dlatego 0,006 USD to górna
granica, a dolna to ok. 0,003 USD.

**Czynniki zwiększające koszt:** zgłoszenie z 4 twierdzeniami, zrzut ekranu (dodatkowy OCR), dwie rundy doprecyzowania.
**Czynniki zmniejszające koszt:** powtórzone zgłoszenie w ciągu 24 h (`RESULT_CACHE_HOURS`) i ten sam obraz w ciągu 24 h
(`IMAGE_CACHE_HOURS`) są obsługiwane z pamięci wyników bez wywołania modelu. Treść, w której Bielik nie
znajdzie twierdzeń, zostaje odrzucona przed wywołaniem płatnego modelu.

## 2. Koszt 1 000 zapytań: model domyślny i możliwość migracji

Dostawcę modelu zmienia się w panelu moderatora albo w `.env`, bez zmian w kodzie
(`backend/app/llm/catalog.py`). Szacunek przy tym samym założeniu (8 tys. tokenów wejścia, 3 tys. wyjścia):

| Model | Cennik (USD / 1 mln tokenów: wejście / wyjście) | ~ 1 000 zapytań | Miejsce przetwarzania |
|---|---|---|---|
| **DeepSeek V4.1 Flash (używany)** | 0,30 / 1,20 (poza szczytem połowa) | **3–6 USD** | Chiny, poza EOG |
| DeepSeek V4 Pro | 1,32 / 3,96 | ok. 22 USD | Chiny, poza EOG |
| GPT-5.2 mini | 0,25 / 2,00 | ok. 8 USD | USA, poza EOG |
| Gemini 3 Flash | 0,30 / 2,50 | ok. 10 USD | USA, poza EOG |
| Model lokalny (Ollama/vLLM, np. Bielik) | – | 0 USD za API | nasz serwer, może być w EOG |

DeepSeek wybraliśmy, bo przy porównywalnej jakości jest najtańszy. Jeśli dane mają być przetwarzane
w EOG, trzeba przejść na model lokalny. Wtedy koszt API znika, a jego miejsce zajmuje serwer z GPU (sekcja 4).

## 3. Usługi zewnętrzne: koszt, zakres, retencja i ograniczenia

| Usługa | Do czego służy | Co wysyłamy | Koszt | Ograniczenia |
|---|---|---|---|---|
| DeepSeek API | wydzielanie twierdzeń, ocena dowodów, OCR | tekst zgłoszenia po maskowaniu danych osobowych, fragmenty źródeł, zrzut ekranu (tylko do OCR) | wg tokenów (sekcja 2) | przetwarzanie w Chinach; retencję określa regulamin dostawcy; bez klucza lub przy awarii użytkownik dostaje jawny komunikat o błędzie technicznym, nigdy werdykt |
| Google Fact Check Tools API | istniejące fact-checki jako kontekst wspierający | zapytanie tekstowe | 0 USD (wymaga klucza; obowiązują limity Google) | tylko kontekst, nigdy nie nadpisuje oceny twierdzeń |
| Yandex, TinEye przez bibliotekę PicImageSearch | odwrotne wyszukiwanie obrazu | przesłany obraz (zmniejszony do maks. 1600 px) | 0 USD, bez klucza API | **nieoficjalny dostęp bez SLA**: może przestać działać albo zostać zablokowany; obraz trafia do Yandex (Rosja) i TinEye (Kanada), czyli poza EOG; wyszukiwanie obejmuje tylko indeksy tych dwóch wyszukiwarek |

**Retencja po naszej stronie:** nie zapisujemy przesłanych obrazów. Wynik sprawdzenia jest przechowywany
przez `RETENTION_DAYS=30` dni, a fragmenty archiwalne przez `ARCHIVE_RETENTION_DAYS=30` dni.

**Przed pilotażem:** odwrotne wyszukiwanie obrazu trzeba przenieść na oficjalne, płatne API (np. TinEye API
albo Google Cloud Vision Web Detection) albo na lokalny indeks perceptual hash. Koszt takiego API trzeba
dopisać tutaj po wyborze dostawcy.

## 4. Infrastruktura

Całość działa na jednym serwerze z Dockerem (`docker-compose.yml`):

| Komponent | Wymagania (orientacyjnie) |
|---|---|
| Backend FastAPI + embeddingi (ok. 220 MB) + Whisper `small` (int8, CPU) | 2–3 GB RAM |
| Ollama z Bielikiem 4.5B (kwantyzacja Q8) | ok. 5 GB RAM, najwięcej obciąża CPU |
| PostgreSQL 17 + pgvector | 1–2 GB RAM |
| Frontend Next.js | ok. 0,5 GB RAM |
| Bot Discord (Node.js) | ok. 0,2 GB RAM |

**Rekomendacja:** maszyna wirtualna w centrum danych w UE z 16 GB RAM i 4–8 vCPU, bez GPU.
Miesięczny koszt: **[do uzupełnienia po wyborze dostawcy]**. Do tego domena i certyfikat TLS
(Let's Encrypt jest bezpłatny).

**Wariant z modelem lokalnym zamiast DeepSeek:** potrzebny jest serwer z GPU. To podnosi koszt stały,
ale koszt jednego zapytania spada do zera. Opłaca się przy dużym wolumenie albo gdy przetwarzanie
w EOG jest warunkiem wdrożenia.

## 5. Kanały

| Kanał | Koszt dla obywatela | Koszt utrzymania |
|---|---|---|
| WWW | 0 zł | w cenie serwera |
| Discord (`/fact-check`) | 0 zł | 0 USD: API Discorda jest bezpłatne, bot działa na tym samym serwerze i korzysta z tego samego backendu |

Oba kanały wywołują tę samą logikę weryfikacji, więc nie podwajają kosztu modelu.

## 6. Skalowanie

Koszt modelu rośnie liniowo z liczbą zapytań. Koszt serwera jest stały do momentu, w którym jedna
instancja przestaje wystarczać.

| Zapytań miesięcznie | Model (DeepSeek Flash, szczyt) | Model (poza szczytem) |
|---|---|---|
| 1 000 | ok. 6 USD | ok. 3 USD |
| 10 000 | ok. 60 USD | ok. 30 USD |
| 100 000 | ok. 600 USD | ok. 300 USD |

Pamięć wyników obniża te kwoty o odsetek powtórzonych zgłoszeń, który przy viralowych treściach bywa wysoki.

**Wąskie gardła przy większym ruchu:**

1. **Bielik na CPU.** Jedna instancja Ollamy obsługuje zapytania po kolei. Przy większym ruchu trzeba
   go przenieść na GPU albo wyłączyć wstępne sprawdzenie.
2. **Limity API DeepSeek.** Przy awarii albo przekroczeniu limitu użytkownik dostaje jawny komunikat
   o błędzie, nie werdykt. Zapasowego dostawcę można przełączyć w panelu.
3. **Limit żądań** (`RATE_LIMIT_PER_MINUTE=10` na klienta) działa w pamięci jednego procesu. Przy wielu
   instancjach trzeba go przenieść do Redis.

Poza bazą usługa jest bezstanowa, więc można uruchomić kolejne instancje backendu za load balancerem.

## 7. Pomiar

Wymagania konkursu (sekcja 6) każą podać koszt **deklarowany i zmierzony**. Każda odpowiedź zapisuje
zużyte tokeny i koszt w `meta.cost_usd`, a panel moderatora (`GET /api/v1/admin/metrics`) pokazuje
koszt na 1 000 zapytań.

```bash
cd backend
uv run python -m eval.run_eval     # zestaw referencyjny → eval/out/report.json, pole cost_usd_per_100
uv run python -m eval.benchmark --n 20   # wymaga działającego backendu; koszt łączny i koszt 1 000 zapytań
```

| Miernik | Deklarowany | Zmierzony |
|---|---|---|
| Koszt 100 testów | 0,30–0,60 USD | _do zmierzenia_ |
| Koszt 1 000 zapytań | 3–6 USD | _do zmierzenia_ |
| Średnia liczba tokenów na zapytanie (wejście / wyjście) | 8 000 / 3 000 | _do zmierzenia_ |
| Data pomiaru, model, pora (szczyt / poza szczytem) | – | _do uzupełnienia_ |
