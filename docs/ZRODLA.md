# Źródła

Jedynym miejscem, przez które dokument może trafić do korpusu, jest katalog
[`backend/data/sources.yaml`](../backend/data/sources.yaml). Ten sam katalog jest dostępny do audytu
w interfejsie (`/zrodla`) i przez API (`GET /api/v1/sources`).

## Korpus demonstracyjny

Stan na 2026-11-21 (wersja `10d51f43c4ec`, szczegóły w `backend/data/corpus/manifest.json`):
**575 dokumentów, 11 domen, 4 typy źródeł** (urzędowe 109, akty prawne 80, fact-checking 271, media 115).
Korpus jest wyłącznie polskojęzyczny. Wszystkie rekordy zostały pobrane automatycznie z prawdziwych
serwisów – nie ma w nim treści napisanych przez zespół ani wygenerowanych przez model.
Domeny liczymy na poziomie serwisu (np. `cyfrowa.rp.pl` i `rp.pl` to jedna domena).

| Źródło | Typ | Poziom | Dok. | Co przechowujemy | Licencja / podstawa |
|---|---|---|---|---|---|
| MSZ – aktualności (gov.pl) | urzędowe | 1 | 59 | pełny tekst | CC BY-SA 4.0 (stopka gov.pl) |
| Dziennik Ustaw – API ELI Sejmu | akt prawny | 1 | 80 | tytuł, typ, status, daty | materiał urzędowy (art. 4 pr. aut.) |
| CERT Polska | urzędowe | 1 | 40 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| Konkret24 | fact-checking | 2 | 30 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| Pravda – artykuły | fact-checking | 2 | 20 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| Pravda – ClaimReview | fact-checking | 2 | 211 | twierdzenie, ocena, link | dane strukturalne opublikowane przez wydawcę |
| FakeNews.pl | fact-checking | 2 | 10 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| Ośrodek Studiów Wschodnich – analizy | urzędowe | 1 | 10 | tytuł, zajawka, link | do potwierdzenia – tylko fragment |
| Rzeczpospolita | media | 3 | 20 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| CyberDefence24 | media | 3 | 40 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| Defence24 | media | 3 | 40 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| Niebezpiecznik | media | 3 | 15 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |

Rekordy ClaimReview pochodzą z publicznego kanału danych Google Fact Check Tools
(`datacommons-feeds/factcheck`), do którego wydawcy sami zgłaszają oceny w formacie schema.org/ClaimReview.
Część z nich zawiera adresy, pod którymi pojawiło się sprawdzane twierdzenie (211 rekordów) – to one tworzą
**katalog incydentów** używany do dopasowań URL/domeny. Plik organizatora z bazą incydentów można dołączyć
tym samym mechanizmem (rekord z `claim_reviewed`, `rating` i `appearance_urls`).

## Zasady kwalifikowania, aktualizowania i wykluczania

Pełna treść zasad jest w polu `rules` katalogu. W skrócie:

- **Poziom 1** – źródła pierwotne i urzędowe; **poziom 2** – organizacje fact-checkingowe deklarujące
  standardy IFCN/EFCSN; **poziom 3** – media, tylko jako kontekst. Reguły werdyktu to wymuszają:
  cytat z mediów jest zawsze pokazywany jako „kontekst” i sam nie może potwierdzić ani obalić twierdzenia.
- Każdy wpis ma uzasadnienie kwalifikacji, licencję, politykę przechowywania i politykę aktualizacji.
- Treści otwarte i urzędowe przechowujemy w całości; treści chronione – tylko tytuł, krótki fragment i link
  albo dane strukturalne. Odpowiedź zawsze prowadzi do oryginału.
- Szanujemy `robots.txt` i blokady serwisów. Nie obchodzimy zabezpieczeń ani paywalli.
- Status źródła (np. sankcje UE – `backend/data/source_status.yaml`) i obecność domeny w katalogu incydentów
  wywołują najwyżej neutralne ostrzeżenie. Dopasowanie domeny pokazujemy dopiero od 3 opisanych przypadków
  i nigdy dla platform (Facebook, X, YouTube itd.).
- Źródło usuwamy z katalogu, gdy traci status będący podstawą kwalifikacji lub zmienia warunki korzystania.
  Jego dokumenty znikają z korpusu przy następnej aktualizacji.

## Źródła rozważone, ale nieujęte w katalogu

Te serwisy spełniają kryteria merytoryczne, ale nie pozwalają na automatyczne pobieranie, więc nie ma ich
ani w katalogu, ani w korpusie. Po uzgodnieniu dostępu wystarczy dodać wpis do `sources.yaml`.

| Źródło | Powód |
|---|---|
| Demagog | serwis blokuje automatyczne pobieranie (HTTP 403) |
| AFP Sprawdzam | jw. |
| Rada UE – komunikaty | kontrola przeglądarki także dla `robots.txt` |

## Aktualizacja

```bash
cd backend
uv run python -m app.ingest.run                 # wszystkie źródła z katalogu (kanał ClaimReview to ok. 200 MB)
uv run python -m app.ingest.run --only konkret24,msz-gov-pl
```

Przebieg dopisuje nowe dokumenty, zapisuje datę pobrania każdego rekordu i raport w `manifest.json`.
Zmiana korpusu zmienia jego wersję, co unieważnia pamięć wyników i wymusza przeliczenie indeksu.
W prototypie aktualizację uruchamia się ręcznie lub z crona; częstotliwości z katalogu są docelowe.

## Do zrobienia przed pilotażem

- Przegląd prawny licencji (zwłaszcza zakres użycia danych ClaimReview i fragmentów treści chronionych).
- Potwierdzenie statusu IFCN/EFCSN każdej redakcji w oficjalnych rejestrach (w katalogu oznaczone jako deklaracja).
- Uzgodnienie dostępu do źródeł nieujętych w katalogu oraz dołączenie pakietu źródeł i bazy incydentów organizatora.
- Rozszerzenie polskich źródeł pierwotnych: dane.gov.pl, GUS, BIP, kolejne urzędy i redakcje fact-checkingowe.
- OSW zakwalifikowano jako instytucję państwową (poziom 1), choć publikuje analizy, a nie dokumenty urzędowe – do decyzji, czy nie powinien to być poziom 2.
- Kanał BIP Rzecznika Praw Obywatelskich odrzucono: zawiera głównie wpisy rejestrowe z nazwiskami osób.
