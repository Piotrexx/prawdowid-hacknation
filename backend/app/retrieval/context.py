"""Kontekst niebędący dowodem: dopasowania do znanych incydentów i status źródła.

Nic z tego modułu nie trafia do reguł werdyktu – wynik jest pokazywany obok oceny.
Dane incydentów pochodzą z tabeli `articles` (rekordy ClaimReview), a nie z pliku
katalogu.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, datetime
from urllib.parse import urlsplit

from app.retrieval.corpus import CorpusDocument, CorpusStore
from app.retrieval.embeddings import Embedder
from app.schemas import IncidentMatch, Warning
from app.security.source_status import SOURCE_STATUSES
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


def _incident(doc: CorpusDocument, match_type: str, note: str) -> IncidentMatch:
    published = doc.published_at.date() if doc.published_at else None
    return IncidentMatch(
        incident_id=doc.doc_id,
        match_type=match_type,  # type: ignore[arg-type]
        title=doc.claim_reviewed or doc.title,
        publisher=doc.publisher,
        url=doc.url,
        date=published,
        note=note,
    )


class ContextIndex:
    def __init__(self, corpus: CorpusStore, embedder: Embedder | None):
        self._corpus = corpus
        self._embedder = embedder
        self._by_url: dict[str, CorpusDocument] = {}
        self._by_domain: dict[str, list[CorpusDocument]] = defaultdict(list)
        self.reload()

    def reload(self) -> None:
        self._by_url.clear()
        self._by_domain.clear()
        for doc in self._corpus.factcheck_documents():
            for url in {doc.url, *doc.appearance_urls}:
                self._by_url.setdefault(_url_key(url), doc)
                domain = domain_of(url)
                if domain and domain not in PLATFORM_DOMAINS:
                    self._by_domain[domain].append(doc)

    def url_matches(self, url: str) -> list[IncidentMatch]:
        exact = self._by_url.get(_url_key(url))
        if exact:
            return [
                _incident(
                    exact,
                    "url",
                    f"Ten adres został już opisany w weryfikacji (ocena redakcji: {exact.rating or 'brak oceny'}).",
                )
            ]
        incidents = {d.doc_id: d for d in self._by_domain.get(domain_of(url), [])}
        if len(incidents) < DOMAIN_MIN_INCIDENTS:
            return []
        newest = max(
            incidents.values(),
            key=lambda d: d.published_at or d.retrieved_at or datetime.min.replace(tzinfo=UTC),
        )
        return [
            _incident(
                newest,
                "domain",
                f"Materiały z tej domeny były opisane w {len(incidents)} zweryfikowanych przypadkach. "
                "To informacja o domenie, a nie ocena tej treści.",
            )
        ]

    def content_matches(self, claim: str, candidates: list[CorpusDocument]) -> list[IncidentMatch]:
        reviewed = list({d.doc_id: d for d in candidates if d.claim_reviewed}.values())
        if not reviewed:
            return []
        vectors = (
            self._embedder.embed_documents([claim, *(d.claim_reviewed or "" for d in reviewed)])
            if self._embedder is not None
            else None
        )
        matches = []
        for index, doc in enumerate(reviewed):
            if vectors is not None:
                similar = _cosine(vectors[0], vectors[index + 1]) >= _CONTENT_MIN_COSINE
            else:
                similar = jaccard(claim, doc.claim_reviewed or "") >= _CONTENT_MIN_JACCARD
            if similar:
                matches.append(
                    _incident(
                        doc,
                        "content",
                        f"Podobne twierdzenie było już sprawdzane (ocena redakcji: {doc.rating or 'brak oceny'}).",
                    )
                )
        return matches

    def source_status(self, url: str) -> Warning | None:
        domain = domain_of(url)
        for entry in SOURCE_STATUSES:
            if any(domain == d or domain.endswith(f".{d}") for d in entry["domains"]):
                return Warning(
                    code="source_status",
                    message=(
                        f"Uwaga o statusie źródła: {entry['status']} "
                        f"({entry['basis']}; {entry['reference_url']}). "
                        "Ten status nie przesądza o prawdziwości konkretnej treści."
                    ),
                )
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
