# Prawdowid — lista zadań

## A. Natychmiastowe i logowanie

- [ ] **A1** Logowanie surowej odpowiedzi trafilatury
- [ ] **A2** Czas odpowiedzi każdego modelu osobno
- [ ] **A3** Zejść do mediany ≤ 30 s

## B. Pętla informacji

- [ ] **B1** Przywrócić core/cases.py
- [ ] **B2** Przywrócić tabele spraw i metody store’a
- [ ] **B3** Przywrócić CaseOut, ModeratorCaseInfo i risk w schemas.py
- [ ] **B4** Ustawienia: case_loop_enabled, case_notify_threshold, moderator_webhook_url
- [ ] **B5** Pipeline rejestruje nierozstrzygnięte twierdzenia
- [ ] **B6** Rozdzielić rekomendację od faktycznego przekazania
- [ ] **B7** notified tylko przy odpowiedzi webhooka < 300
- [ ] **B8** asyncio.Lock wokół znajdź-lub-utwórz
- [ ] **B9** Panel moderatora: kolejka spraw
- [ ] **B10** Alert o powtarzających się pytaniach bez odpowiedzi
- [ ] **B11** Test scenariusza H
- [ ] **B12** Deduplikacja wymaga embeddingów

## C. Poprawność werdyktu i dowody

- [ ] **C1** Znormalizowane odpowiedzi z bazy
- [ ] **C2** Taksonomia werdyktów nie zgadza się z wymaganiami
- [ ] **C3** Łańcuch dowodowy: każda teza prowadzi do źródła
- [ ] **C4** Siła podstawy odpowiedzi z jawnych przesłanek
- [ ] **C5** Obsługa sprzeczności źródeł
- [ ] **C6** Ostrzeżenie o materiale archiwalnym
- [ ] **C7** confidence nie może udawać pewności

## D. Wydzielanie twierdzeń

- [ ] **D1** Rozpoznawanie jednego lub kilku twierdzeń
- [ ] **D2** Rozdzielenie faktu, opinii i prognozy

## E. Źródła i korpus

- [ ] **E1** Otwarty, wymienny katalog źródeł
- [ ] **E2** Przywrócić korpus demonstracyjny
- [ ] **E3** Przywrócić wyszukiwanie: BM25 + embeddingi + RRF
- [ ] **E4** Przywrócić ingest: 11 konektorów
- [ ] **E5** Przywrócić GET /api/v1/sources i stronę /zrodla
- [ ] **E6** Status źródła jako osobne, neutralne ostrzeżenie
- [ ] **E7** Katalog incydentów i dopasowania URL / domena / treść
- [ ] **E8** Źródło legislacyjne — robi kolega
- [ ] **E9** Rozszerzenie źródeł pierwotnych i urzędowych
- [ ] **E10** Korpusy organizacji fact-checkingowych
- [ ] **E11** Pakiet źródeł i baza incydentów organizatora
- [ ] **E12** Wielojęzyczne wyszukiwanie z odpowiedzią po polsku

## F. Bezpieczeństwo i prompt injection

- [ ] **F1** Przywrócić security/injection.py
- [ ] **F2** Bloki danych o losowej nazwie znacznika
- [ ] **F3** Flaga injection od modelu → ostrzeżenie i zdarzenie
- [ ] **F4** Maskowanie danych osobowych po stronie backendu
- [ ] **F5** Lista zdarzeń bezpieczeństwa w panelu moderatora

## G. Multimodalność: obraz, OCR, dźwięk

- [ ] **G1** Przywrócić core/media.py
- [ ] **G2** POST /checks z obrazem (multipart)
- [ ] **G3** OCR i odczyt tekstu z obrazu
- [ ] **G4** Wyszukiwanie wcześniejszych wystąpień obrazu
- [ ] **G5** Transkrypcja dźwięku po stronie usługi
- [ ] **G6** Analiza metadanych obrazu i porównywanie obrazów
- [x] **G7** Wejście obrazem: zwykły wybór pliku, nie dyktafon

## H. Kanały komunikacji

- [ ] **H1** Bot Discord
- [ ] **H2** Spójność między kanałami
- [ ] **H3** channel nie może być zahardkodowany

## I. Poprawki frontendu

- [ ] **I1** Wejście głosowe: nagranie, nie dyktafon
- [ ] **I2** System toastów w stylu chunky
- [ ] **I3** Wybrać sposób transkrypcji na frontendzie
- [ ] **I4** Popup zgody przed jakimkolwiek zapisem
- [ ] **I5** Przełącznik modelu — zostaje bez zmian
- [ ] **I6** Usunąć przejściówkę adaptResponse()

## J. Integracje analityczne

- [ ] **J1** Integracja z OpenCTI
- [ ] **J2** Integracja z DISARM
- [ ] **J3** Rozszerzyć kolumny eksportu

## K. Zapis przebiegu sprawdzenia

- [ ] **K1** Zapis przebiegu bez wykorzystanych źródeł jest niepełny
- [ ] **K2** Luki w obserwowalności

## L. Zgodność i polityki

- [ ] **L1** Dokumentacja musi opisywać stan faktyczny
- [ ] **L2** Zgoda użytkownika warunkiem zapisu
- [ ] **L3** Kontrolowana archiwizacja materiału wskazanego przez użytkownika
- [ ] **L4** Ograniczenie zależności od dostawców spoza EOG
- [ ] **L5** Przegląd prawny licencji korpusu

## M. Testy i ewaluacja

- [ ] **M1** 23 z 32 testów backendu nie da się uruchomić
- [ ] **M2** Zestaw testowy: z 4 przypadków do co najmniej 30
- [ ] **M3** Zmierzyć wszystkie mierniki obowiązkowe
- [ ] **M4** Przywrócić tests/test_llm_providers.py
- [ ] **M5** factory.py jest zepsute dla LLM_PROVIDER=anthropic

## N. Funkcja drzewa binarnego

- [ ] **N1** Funkcja drzewa binarnego zdarzeń

## O. Wymagania formalne zgłoszenia

- [ ] **O1** Nazwa zespołu, tytuł i opis do 4 000 znaków
- [ ] **O2** Prezentacja PDF, maksymalnie 12 slajdów
- [ ] **O3** Film demonstracyjny do 3 minut pod linkiem
- [ ] **O4** Link do repozytorium z instrukcją uruchomienia
- [ ] **O5** Opis architektury, przepływu danych, modeli i dostawców
- [ ] **O6** Opis źródeł, licencji, kwalifikacji i aktualizacji
- [ ] **O7** Wyniki testów z danymi pozwalającymi odtworzyć rezultat
- [x] **O8** Lista najważniejszych ryzyk
- [ ] **O9** Sprawdzić, że w repozytorium nie ma kluczy ani sekretów

## Z. Zrobione: fundament

- [x] **Z1** Szkielet: FastAPI, Next.js 16, docker-compose z Ollamą
- [x] **Z2** Warstwa abstrakcji nad modelem (protokół LLMProvider)
- [x] **Z3** Dostawca zgodny z OpenAI: DeepSeek, Mistral, Ollama, vLLM, OpenRouter
- [x] **Z4** Szacowanie kosztu per model z nadpisaniem z env
- [x] **Z5** Ochrona przed SSRF w pobieraniu URL
- [x] **Z6** Respektowanie robots.txt z cache’em TTL
- [x] **Z7** Ekstrakcja treści trafilaturą z metadanymi i datą publikacji
- [x] **Z8** Awaria techniczna oddzielona od werdyktu
- [x] **Z9** Fallback na DeepSeeka, gdy model lokalny nie odpowiada
- [x] **Z10** needs_clarification dla zbyt krótkiego tekstu
- [x] **Z11** Limit żądań na klienta i nagłówek Retry-After
- [x] **Z12** Retencja: czyszczenie co godzinę i usuwanie sesji
- [x] **Z13** Nagłówki bezpieczeństwa, allowlista CORS, token moderatora
- [x] **Z14** Baza SQLite przez SQLAlchemy, wymienna na Postgresa
- [x] **Z15** Log JSON na każde sprawdzenie
- [x] **Z16** Panel moderatora: metryki, lista sprawdzeń, eksport
- [x] **Z17** Interfejs czatu: autoskalowanie, wklejanie, przeciąganie plików
- [x] **Z18** Komponenty wyniku gotowe na pełny kontrakt
- [x] **Z19** Dostępność: rozmiar tekstu, wysoki kontrast, aria-live
- [x] **Z20** Permalink wyniku, historia lokalna, cache wyniku
- [x] **Z21** Maskowanie danych osobowych w przeglądarce
- [x] **Z22** Strona /prywatnosc i /o-systemie
- [x] **Z23** Odpowiedzi i interfejs wyłącznie po polsku
