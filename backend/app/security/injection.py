"""Heurystyczne wykrywanie prób prompt injection w treściach niezaufanych.

Wykrycie niczego nie blokuje – treść i tak jest traktowana wyłącznie jako dane.
Służy do odnotowania zdarzenia i poinformowania użytkownika.
"""

import re
import secrets

from app.textutil import fold

# Wzorce zapisane bez znaków diakrytycznych: dopasowujemy je do tekstu po `fold()`.
_PATTERNS = [
    r"ignore (?:all |any |the |your |these |those )*(?:previous|prior|above|earlier|preceding)? ?(?:instructions|rules|prompts|guidelines)",
    r"disregard (?:all |any |the |your )*(?:previous |prior |above )?(?:instructions|rules|system prompt|guidelines)",
    r"forget (?:all |everything |your )*(?:previous |prior )?(?:instructions|rules)",
    r"(?:override|bypass) (?:your |the |all )*(?:rules|instructions|safety|guidelines)",
    r"you are now\b",
    r"new (?:system )?instructions\s*:",
    r"system prompt",
    r"developer mode|jailbreak",
    r"</?\s*(?:system|assistant|instructions?|user)\s*>",
    r"(?:answer|respond|reply|say|state|output) (?:only )?(?:that|with)\b.{0,60}\b(?:true|confirmed|verified|false)",
    r"(?:mark|rate|label|classify) (?:this|the|it)\b.{0,40}\bas (?:true|confirmed|verified|false)",
    # Polskie warianty (bez diakrytyków po fold()):
    r"zignoruj (?:\w+ ){0,5}(?:instrukcj|polecen|zasad|regul|wytyczn|poprzedni)",
    r"(?:pomin|zapomnij o|nie stosuj sie do|zlekcewaz|olewaj|odrzuc) (?:\w+ ){0,3}(?:instrukcj|polecen|zasad|regul|wytyczn)",
    r"jestes teraz\b",
    r"nowe (?:instrukcje|polecenia|zasady|regul|wytyczne)\s*:",
    r"(?:prompt|instrukcj\w*|polecen\w*|zasad\w*) systemow",
    r"(?:odpowiedz|napisz|stwierdz|powiedz|zwroc|wyswietl),? ze\b.{0,80}\b(?:prawd|potwierdz|falsz|zweryfikowan|wprowadzajac)",
    r"(?:oznacz|ocen|uznaj|zaklasyfikuj|sklasyfikuj|zapisz) (?:\w+ ){0,5}jako (?:prawdziw|potwierdzon|falszyw|zweryfikowan|wprowadzajac)",
    r"(?:wypisz|ujawnij|pokaz|pokaze?|podaj|wyswietl) (?:\w+ ){0,3}(?:prompt|instrukcje|polecenia|zasad|wytyczne)",
    # Ataki markowane słowem SYSTEM/ASYSTENT na początku linii (po fold: wszystkie małe litery):
    r"(?:^|\n|\.|\!|\?|:)\s*(?:system|asystent|assistant|ai|chatbot|model|instrukcja)\s*[:=\-–—]\s*",
    # Ujawnianie konfiguracji / szablonu:
    r"(?:reveal|show|print|leak|dump|disclose) (?:your |the |all )*(?:prompt|system|instruction|guideline|rule)",
    r"(?:ujawnij|pokaz|wyswietl|wypisz|wyjaw) (?:\w+ ){0,3}(?:prompt|szablon|konfiguracj|ustawien|regul)",
    # Bezpośrednie prośby o werdykt / rozstrzygnięcie bez źródeł:
    r"(?:return|give me|produce|output|generate) (?:a |the )?(?:verdict|answer)\s*[:=]?\s*(?:true|false|confirmed|refuted)",
    r"(?:zwroc|podaj|wygeneruj|wypisz) (?:werdykt|ocene|wynik|odpowiedz)\s*[:=]?\s*(?:prawd|falsz|potwierdz|wprowadzajac)",
    # Role play / manipulacje tożsamością:
    r"act as (?:a |an )?(?:different|new|another|unrestricted|uncensored)",
    r"udawaj (?:innego|innej|nieograniczonego|bez ograniczen)",
    r"pretend (?:to be|you are) (?:a |an )?(?:different|new|unrestricted|uncensored|no restriction)",
    # Ataki w stylu DAN / „wyjdź z charakteru":
    r"stay in character|break character|out of character|wyjdz z roli",
]
_INJECTION_RE = re.compile("|".join(f"(?:{p})" for p in _PATTERNS))
# Znaki niewidoczne i sterujące bywają używane do ukrywania poleceń w treści.
_INVISIBLE_RE = re.compile(r"[​-‏‪-‮⁠-⁤﻿\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_untrusted(text: str) -> str:
    return _INVISIBLE_RE.sub("", text)


def scan_injection(text: str) -> list[str]:
    """Zwraca dopasowane fragmenty (po normalizacji) – pusty wynik oznacza brak sygnału."""
    folded = fold(sanitize_untrusted(text))
    return list(dict.fromkeys(m.group(0)[:120] for m in _INJECTION_RE.finditer(folded)))[:5]


def wrap_untrusted(label: str, text: str) -> tuple[str, str]:
    """Otacza treść znacznikiem z losowym identyfikatorem, którego treść nie może odgadnąć,
    więc nie jest w stanie „zamknąć” bloku danych i udawać instrukcji."""
    tag = f"{label}-{secrets.token_hex(6)}"
    return tag, f"<{tag}>\n{sanitize_untrusted(text)}\n</{tag}>"
