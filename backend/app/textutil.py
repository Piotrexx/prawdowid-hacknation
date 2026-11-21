"""Utility functions for text processing."""

import re

# Końcówki, pod którymi instytucje rejestrują własne domeny (np. sejm.gov.pl, pravda.org.pl).
_SHARED_SUFFIXES = frozenset({"gov.pl", "org.pl", "com.pl", "net.pl", "edu.pl", "waw.pl"})


def truncate(text: str, limit: int) -> str:
    """Skraca tekst do limitu znaków, cięcie na granicy słowa z wielokropkiem."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def site_domain(url: str) -> str:
    """Domena serwisu bez poddomen, żeby np. cyfrowa.rp.pl i rp.pl liczyć jako jedno źródło."""
    from urllib.parse import urlsplit
    labels = (urlsplit(url).hostname or "").lower().removeprefix("www.").split(".")
    keep = 3 if len(labels) > 2 and ".".join(labels[-2:]) in _SHARED_SUFFIXES else 2
    return ".".join(labels[-keep:])