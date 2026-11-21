"""Przybliżone mapowanie wyników Prawdowida na techniki DISARM.

DISARM opisuje zachowania w kampaniach dezinformacyjnych; werdykt o pojedynczym
twierdzeniu nie jest diagnozą kampanii. Mapowanie służy do eksportu analitycznego
i jest jawnie oznaczone jako pomocnicze (`x_disarm_unmapped` przy braku pewności).
"""

from __future__ import annotations

DISARM_MAPPING: dict[str, list[dict]] = {
    "falszywe": [
        {"technique_id": "T0019", "name": "Generate Content", "confidence": "low"},
        {"technique_id": "T0086", "name": "Distort Facts", "confidence": "low"},
    ],
    "wprowadzajace_w_blad": [
        {"technique_id": "T0086", "name": "Distort Facts", "confidence": "low"},
        {"technique_id": "T0002", "name": "Vulnerabilities", "confidence": "low"},
    ],
    "brak_wystarczajacych_dowodow": [],
    "potwierdzone": [],
    "nie_podlega_weryfikacji": [],
}


def disarm_for_verdict(verdict: str) -> list[dict]:
    """Zwraca listę technik; pusta lista oznacza brak przypisania, nie „brak zagrożenia”."""
    return list(DISARM_MAPPING.get(verdict, []))


def disarm_summary(verdict: str) -> dict:
    techniques = disarm_for_verdict(verdict)
    if techniques:
        return {"techniques": techniques}
    return {"unmapped": True, "reason": "Brak wystarczającej pewności dla mapowania DISARM."}
