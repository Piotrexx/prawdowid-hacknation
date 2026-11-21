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
    r"</?\s*(?:system|assistant|instructions?)\s*>",
    r"(?:answer|respond|reply|say|state|output) (?:only )?(?:that|with)\b.{0,60}\b(?:true|confirmed|verified|false)",
    r"(?:mark|rate|label|classify) (?:this|the|it)\b.{0,40}\bas (?:true|confirmed|verified|false)",
    r"zignoruj (?:\w+ ){0,3}(?:instrukcje|polecenia|zasady|reguly|wytyczne)",
    r"(?:pomin|zapomnij o|nie stosuj sie do|zlekcewaz) (?:\w+ ){0,3}(?:instrukcj|polecen|zasad|regul|wytyczn)",
    r"jestes teraz\b",
    r"nowe (?:instrukcje|polecenia|zasady)\s*:",
    r"(?:prompt|instrukcj\w*|polecen\w*) systemow",
    r"(?:odpowiedz|napisz|stwierdz|powiedz|zwroc),? ze\b.{0,60}\b(?:prawd|potwierdz|falsz|zweryfikowan)",
    r"(?:oznacz|ocen|uznaj|zaklasyfikuj) (?:\w+ ){0,3}jako (?:prawdziw|potwierdzon|falszyw|zweryfikowan)",
    r"(?:wypisz|ujawnij|pokaz) (?:\w+ ){0,2}(?:prompt|instrukcje|polecenia)",
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
