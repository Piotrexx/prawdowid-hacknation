"""Maskowanie oczywistych danych osobowych przed zapisem i przed wysłaniem do modelu."""

import re
from collections import Counter

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_ACCOUNT = re.compile(r"\b(?:PL ?)?\d{2}(?: ?\d{4}){6}\b")
_CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
_PESEL = re.compile(r"\b\d{11}\b")
_PHONE = re.compile(r"(?<![\d+])(?:(?:\+|00)48[ -]?)?[4-8]\d{2}[ -]?\d{3}[ -]?\d{3}(?!\d)")

_PESEL_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)


def _valid_pesel(digits: str) -> bool:
    checksum = sum(int(d) * w for d, w in zip(digits, _PESEL_WEIGHTS, strict=False))
    return (10 - checksum % 10) % 10 == int(digits[10])


def _valid_luhn(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()][::-1]
    total = sum(d if i % 2 == 0 else (d * 2 - 9 if d > 4 else d * 2) for i, d in enumerate(digits))
    return total % 10 == 0


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    counts: Counter[str] = Counter()

    def replace(pattern: re.Pattern, label: str, valid=lambda _: True) -> None:
        nonlocal text

        def sub(match: re.Match) -> str:
            if not valid(match.group()):
                return match.group()
            counts[label] += 1
            return f"[{label}]"

        text = pattern.sub(sub, text)

    # Kolejność ma znaczenie: dłuższe ciągi cyfr przed krótszymi, żeby telefon nie „zjadł” konta.
    replace(_EMAIL, "EMAIL")
    replace(_ACCOUNT, "NR_KONTA")
    replace(_CARD, "NR_KARTY", _valid_luhn)
    replace(_PESEL, "PESEL", _valid_pesel)
    replace(_PHONE, "TELEFON")
    return text, dict(counts)
