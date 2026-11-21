"""Prompty dla modeli językowych - wyłącznie w języku polskim."""

# Prompt dla Bielik 4.5B Instruct - ekstrakcja słów kluczowych
BIELIK_KEYWORD_PROMPT = """
Przeanalizuj poniższy artykuł i wyekstrahuj kluczowe informacje do weryfikacji faktów.

Tytuł: {title}

Treść:
{text}

Zadanie:
1. Zidentyfikuj główny temat artykułu (jedno zdanie).
2. Wyekstrahuj do 10 najważniejszych słów kluczowych/fraz, które najlepiej nadają się do wyszukiwania sprawdzeń faktów (fact-checking). Skup się na: nazwiskach, nazwach instytucji, konkretnych twierdzeniach, datach, lokalizacjach, liczbach.
3. Napisz krótkie podsumowanie (2-3 zdania) na czym polega główne twierdzenie artykułu.

Odpowiedz WYŁĄCZNIE obiektem JSON o strukturze:
{{
    "keywords": ["słowo1", "fraza 2", "nazwisko 3", ...],
    "main_topic": "Główny temat artykułu w jednym zdaniu.",
    "summary": "Krótkie podsumowanie głównego twierdzenia."
}}

Ważne:
- Słowa kluczowe muszą być konkretne i przydatne do wyszukiwania w bazach fact-checkingowych
- Unikaj ogólnych słów jak "polityka", "ekonomia", "skandal" - używaj nazw właściwych
- Jeśli artykuł zawiera cytaty - uwzględnij kluczowe fragmenty jako frazy
- Odpowiedz TYLKO po polsku
""".strip()

# Prompt dla DeepSeek - ostateczny werdykt
DEEPSEEK_VERDICT_PROMPT = """
Jesteś ekspertem ds. weryfikacji informacji i wykrywania dezinformacji (fake news).
Twoim zadaniem jest ocena, czy podany artykuł zawiera fake news, na podstawie:
- treści artykułu,
- wyekstrahowanych słów kluczowych,
- znalezionych sprawdzeń faktów z Google Fact Check Tools.

Artykuł do oceny:
Tytuł: {title}

Treść:
{text}

Słowa kluczowe: {keywords}
Główny temat: {main_topic}

{factcheck_context}

Kryteria oceny:
1. FAKE_NEWS - artykuł zawiera fałszywe informacje, które zostały obalone przez wiarygodne fact-checki LUB artykuł jest celowo wprowadzający w błąd (dezinformacja, manipulacja kontekstem, fałszywe przypisywanie cytatów).
2. PRAWDZIWE - główne twierdzenia artykułu są wspierane przez wiarygodne źródła i fact-checki.
3. NIEPEWNE - brak wystarczających dowodów ani w jedną, ani w drugą stronę; twierdzenia są trudne do zweryfikowania lub sprzeczne.
4. SATYRA - artykuł jest satyrą/paryzą, nie ma być traktowany poważnie (np. The Onion, ASZdziennik).
5. OPINIA - artykuł wyraża opinię/komentarz, a nie stwierdza fakty.

Zwróć uwagę na:
- Czy fact-checki bezpośrednio obalają lub potwierdzają twierdzenia z artykułu?
- Czy artykuł wyrywa cytaty z kontekstu?
- Czy używa reisserycznych nagłówków niezgodnych z treścią?
- Czy źródła fact-checków są wiarygodne (renomowane organizacje: Demagog, AFP, Reuters Fact Check, PolitiFact, itp.)?

Odpowiedz WYŁĄCZNIE obiektem JSON o strukturze:
{{
    "verdict": "fake_news" | "prawdziwe" | "niepewne" | "satyna" | "opinia",
    "confidence": 0.0-1.0,
    "justification": "Szczegółowe uzasadnienie werdyktu po polsku, z nawiązaniem do konkretnych fact-checków i fragmentów artykułu. Wyjaśnij dlaczego przyjąłeś taką ocenę."
}}

Ważne:
- confidence to Twoja pewność werdyktu (0.0 - 1.0)
- justification musi być po polsku, konkretna i uzasadniona
- Jeśli fact-checki sprzeczają się ze sobą - wskaż to w uzasadnieniu i obniż confidence
- Odpowiedz TYLKO po polsku
""".strip()