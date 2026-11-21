"""Kontekst niebędący dowodem: dopasowania do znanych incydentów i status źródła.

Nic z tego modułu nie trafia do reguł werdyktu – wynik jest pokazywany obok oceny.
"""

from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from app.catalog import Document
from app.retrieval.index import CorpusIndex
from app.schemas import IncidentMatch, Warning
from app.textutil import jaccard

# Domena platformy nic nie mówi o treści, więc nie budujemy dla niej dopasowań „po domenie”.
PLATFORM_DOMAINS = frozenset(
    """facebook.com m.facebook.com x.com twitter.com youtube.com youtu.be tiktok.com instagram.com
    t.me telegram.org vk.com threads.net threads.com linkedin.com reddit.com rumble.com
    archive.org web.archive.org archive.ph archive.is perma.cc bsky.app truthsocial.com
    whatsapp.com wykop.pl banbye.com bitchute.com""".split()
)
DOMAIN_MIN_INCIDENTS = 3
_CONTENT_MIN_COSINE = 0.78
_CONTENT_MIN_JACCARD = 0.5


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _url_key(url: str) -> str:
    parts = urlsplit(url)
    return f"{domain_of(url)}{parts.path.rstrip('/')}?{parts.query}".rstrip("?")


def _incident(doc: Document, match_type: str, note: str) -> IncidentMatch:
    return IncidentMatch(
        incident_id=doc.id,
        match_type=match_type,
        title=doc.claim_reviewed or doc.title,
        publisher=doc.publisher,
        url=doc.url,
        date=doc.published_at,
        note=note,
    )


class ContextCatalog:
    def __init__(self, index: CorpusIndex, status_path: Path):
        self._index = index
        self._by_url: dict[str, Document] = {}
        self._by_domain: dict[str, list[Document]] = defaultdict(list)
        for doc in index.documents:
            for url in doc.appearance_urls:
                self._by_url.setdefault(_url_key(url), doc)
                domain = domain_of(url)
                if domain and domain not in PLATFORM_DOMAINS:
                    self._by_domain[domain].append(doc)
        statuses = yaml.safe_load(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        self._statuses = (statuses or {}).get("statuses", [])

    def url_matches(self, url: str) -> list[IncidentMatch]:
        exact = self._by_url.get(_url_key(url))
        if exact:
            return [_incident(exact, "url", f"Ten adres został już opisany w weryfikacji (ocena redakcji: {exact.rating or 'brak oceny'}).")]
        incidents = {d.id: d for d in self._by_domain.get(domain_of(url), [])}
        if len(incidents) < DOMAIN_MIN_INCIDENTS:
            return []
        newest = max(incidents.values(), key=lambda d: str(d.published_at or ""))
        return [
            _incident(
                newest,
                "domain",
                f"Materiały z tej domeny były opisane w {len(incidents)} zweryfikowanych przypadkach. "
                "To informacja o domenie, a nie ocena tej treści.",
            )
        ]

    def content_matches(self, claim: str, candidates: list[Document]) -> list[IncidentMatch]:
        reviewed = list({d.id: d for d in candidates if d.claim_reviewed}.values())
        if not reviewed:
            return []
        vectors = self._index.embed([claim, *(d.claim_reviewed for d in reviewed)])
        matches = []
        for i, doc in enumerate(reviewed):
            similar = (
                float(vectors[0] @ vectors[i + 1]) >= _CONTENT_MIN_COSINE
                if vectors is not None
                else jaccard(claim, doc.claim_reviewed) >= _CONTENT_MIN_JACCARD
            )
            if similar:
                matches.append(_incident(doc, "content", f"Podobne twierdzenie było już sprawdzane (ocena redakcji: {doc.rating or 'brak oceny'})."))
        return matches

    def source_status(self, url: str) -> Warning | None:
        domain = domain_of(url)
        for entry in self._statuses:
            if any(domain == d or domain.endswith(f".{d}") for d in entry["domains"]):
                return Warning(
                    code="source_status",
                    message=(
                        f"Uwaga o statusie źródła: {entry['status']} ({entry['basis']}; {entry['reference_url']}). "
                        "Ten status nie przesądza o prawdziwości konkretnej treści."
                    ),
                )
        return None
