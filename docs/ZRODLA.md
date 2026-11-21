# Źródła

Jedynym miejscem, przez które dokument może trafić do korpusu, jest katalog
[`backend/data/sources.yaml`](../backend/data/sources.yaml). Ten sam katalog jest dostępny do audytu
w interfejsie (`/zrodla`) i przez API (`GET /api/v1/sources`).

## Korpus demonstracyjny

Stan na 2026-11-21 (wersja `b5bc0340bb68`, szczegóły w `backend/data/corpus/manifest.json`):
**830 dokumentów, 11 domen, 4 typy źródeł** (urzędowe 109, akty prawne 80, organizacje międzynarodowe 70,
fact-checking 571). Wszystkie rekordy zostały pobrane automatycznie z prawdziwych serwisów – w korpusie
nie ma treści napisanych przez zespół ani wygenerowanych przez model.

| Źródło | Typ | Poziom | Dok. | Co przechowujemy | Licencja / podstawa |
|---|---|---|---|---|---|
| MSZ – aktualności (gov.pl) | urzędowe | 1 | 59 | pełny tekst | CC BY-SA 4.0 (stopka gov.pl) |
| Dziennik Ustaw – API ELI Sejmu | akt prawny | 1 | 80 | tytuł, typ, status, daty | materiał urzędowy (art. 4 pr. aut.) |
| Komisja Europejska – Press Corner | urzędowe | 1 | 10 | tytuł, zajawka, link | CC BY 4.0 (decyzja 2011/833/UE) |
| CERT Polska | urzędowe | 1 | 40 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| WHO – News | org. międzynarodowa | 2 | 60 | fragment, link | CC BY-NC-SA 3.0 IGO |
| ECDC – News | org. międzynarodowa | 2 | 10 | fragment, link | ponowne użycie z podaniem źródła |
| Konkret24 | fact-checking | 2 | 30 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| Pravda – artykuły | fact-checking | 2 | 20 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| Pravda – ClaimReview | fact-checking | 2 | 211 | twierdzenie, ocena, link | dane strukturalne opublikowane przez wydawcę |
| FakeNews.pl | fact-checking | 2 | 10 | tytuł, zajawka, link | prawa zastrzeżone – tylko fragment |
| FactCheck.org – ClaimReview (EN) | fact-checking | 2 | 150 | twierdzenie, ocena, link | dane strukturalne opublikowane przez wydawcę |
| PolitiFact – ClaimReview (EN) | fact-checking | 2 | 150 | twierdzenie, ocena, link | dane strukturalne opublikowane przez wydawcę |

Rekordy ClaimReview pochodzą z publicznego kanału danych Google Fact Check Tools
(`datacommons-feeds/factcheck`), do którego wydawcy sami zgłaszają oceny w formacie schema.org/ClaimReview.
Część z nich zawiera adresy, pod którymi pojawiło się sprawdzane twierdzenie (406 rekordów) – to one tworzą
**katalog incydentów** używany do dopasowań URL/domeny. Plik organizatora z bazą incydentów można dołączyć
tym samym mechanizmem (rekord z `claim_reviewed`, `rating` i `appearance_urls`).

## Zasady kwalifikowania, aktualizowania i wykluczania

Pełna treść zasad jest w polu `rules` katalogu. W skrócie:

- **Poziom 1** – źródła pierwotne i urzędowe; **poziom 2** – organizacje fact-checkingowe deklarujące
  standardy IFCN/EFCSN oraz organizacje międzynarodowe; **poziom 3** – media, tylko jako kontekst.
- Każdy wpis ma uzasadnienie kwalifikacji, licencję, politykę przechowywania i politykę aktualizacji.
- Treści otwarte i urzędowe przechowujemy w całości; treści chronione – tylko tytuł, krótki fragment i link
  albo dane strukturalne. Odpowiedź zawsze prowadzi do oryginału.
- Szanujemy `robots.txt` i blokady serwisów. Nie obchodzimy zabezpieczeń ani paywalli.
- Status źródła (np. sankcje UE – `backend/data/source_status.yaml`) i obecność domeny w katalogu incydentów
  wywołują najwyżej neutralne ostrzeżenie. Dopasowanie domeny pokazujemy dopiero od 3 opisanych przypadków
  i nigdy dla platform (Facebook, X, YouTube itd.).
- Źródło wyłączamy, gdy traci status będący podstawą kwalifikacji lub zmienia warunki korzystania. Wyłączenie
  usuwa jego dokumenty z korpusu przy następnej aktualizacji.

## Źródła zakwalifikowane, ale wyłączone

| Źródło | Powód |
|---|---|
| Demagog | serwis blokuje automatyczne pobieranie (HTTP 403) – potrzebne uzgodnienie dostępu |
| AFP Sprawdzam | jw. |
| EDMO | jw. |
| Rada UE – komunikaty | kontrola przeglądarki także dla `robots.txt` |
| EUvsDisinfo | `robots.txt` zabrania pobierania kanału `/feed/` – czekamy na eksport bazy lub pakiet organizatora |

## Aktualizacja

```bash
cd backend
uv run python -m app.ingest.run                 # wszystkie włączone źródła (kanał ClaimReview to ok. 200 MB)
uv run python -m app.ingest.run --only konkret24,msz-gov-pl
```

Przebieg dopisuje nowe dokumenty, zapisuje datę pobrania każdego rekordu i raport w `manifest.json`.
Zmiana korpusu zmienia jego wersję, co unieważnia pamięć wyników i wymusza przeliczenie indeksu.
W prototypie aktualizację uruchamia się ręcznie lub z crona; częstotliwości z katalogu są docelowe.

## Do zrobienia przed pilotażem

- Przegląd prawny licencji (zwłaszcza zakres użycia danych ClaimReview i fragmentów treści chronionych).
- Potwierdzenie statusu IFCN/EFCSN każdej redakcji w oficjalnych rejestrach (w katalogu oznaczone jako deklaracja).
- Uzgodnienie dostępu do źródeł wyłączonych oraz dołączenie pakietu źródeł i bazy incydentów organizatora.
- Rozszerzenie źródeł pierwotnych: dane.gov.pl, EUR-Lex, GUS, BIP.
