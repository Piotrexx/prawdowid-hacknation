"""Statusy źródeł wywołujące neutralne ostrzeżenie.

Status (np. sankcje UE) nigdy nie przesądza o prawdziwości konkretnej treści.
Wpisy muszą mieć sprawdzalną podstawę i być aktualizowane wraz z prawem.
"""

SOURCE_STATUSES: list[dict] = [
    {
        "domains": ("rt.com", "sputniknews.com"),
        "status": "Nadawca objęty unijnym zakazem rozpowszechniania treści",
        "basis": "rozporządzenie Rady (UE) 2022/350 z 1 marca 2022 r.",
        "reference_url": "https://eur-lex.europa.eu/legal-content/PL/TXT/?uri=CELEX:32022R0350",
    },
]
