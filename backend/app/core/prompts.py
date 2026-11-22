"""Prompty dla modeli językowych - wyłącznie w języku polskim."""

# Prompt dla Bielik 4.5B Instruct - ekstrakcja słów kluczowych
BIELIK_KEYWORD_PROMPT = """
Przeanalizuj poniższy artykuł i wyekstrahuj kluczowe informacje do weryfikacji faktów.

Tytuł: {title}

Treść:
{text}
{clarifications}
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
- Jeśli jest sekcja "Doprecyzowanie od użytkownika", użyj odpowiedzi, żeby wybrać właściwe nazwy i twierdzenia
- Odpowiedz TYLKO po polsku
""".strip()

# Prompt oceniający, czy wiadomo, co sprawdzać (domyślnie DeepSeek, zob. CLARIFICATION_MODEL)
CLARITY_PROMPT = """
Oceń, czy z poniższej treści (artykułu albo wiadomości wklejonej przez użytkownika) da się ustalić, JAKIE konkretne twierdzenie trzeba sprawdzić.

Tytuł: {title}

Treść:
{text}
{clarifications}
Ustaw "needs_clarification": true TYLKO gdy bez dodatkowej informacji nie wiadomo, co sprawdzać, np.:
- treść nie zawiera żadnego konkretnego twierdzenia (np. samo "czy to prawda?", jedno hasło),
- zaimki ("on", "oni", "to") nie mają w treści żadnego odniesienia,
- brakuje kluczowego szczegółu (kto, gdzie, kiedy), bez którego nie da się szukać źródeł.
Pełny artykuł prasowy prawie zawsze da się sprawdzić. Kilka konkretnych twierdzeń w jednej wiadomości też da się sprawdzić – nie pytaj wtedy.
Jeśli jest sekcja "Doprecyzowanie od użytkownika", uwzględnij odpowiedzi i nie pytaj ponownie o to samo.

Gdy "needs_clarification" jest true, zadaj od 1 do 3 krótkich, życzliwych pytań po polsku. Gdy pytanie ma kilka oczywistych odpowiedzi, podaj je w "options". W "missing" wypisz krótko, czego brakuje.
Nie pytaj o dane osobowe użytkownika.

Odpowiedz WYŁĄCZNIE obiektem JSON o strukturze (najpierw "missing", potem decyzja):
{{
    "missing": [],
    "needs_clarification": true | false,
    "questions": []
}}

Przykład dla wiadomości "Podobno on to zrobił, prawda?":
{{
    "missing": ["kto", "co dokładnie się stało"],
    "needs_clarification": true,
    "questions": [{{"text": "O kim jest ta wiadomość?", "options": []}}, {{"text": "Co dokładnie ta osoba miała zrobić?", "options": []}}]
}}
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
{clarifications}
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
- Jeśli jest sekcja "Doprecyzowanie od użytkownika", traktuj ją jako wyjaśnienie, o które twierdzenie chodzi, a nie jako dowód jego prawdziwości
- Odpowiedz TYLKO po polsku
""".strip()