"""Ekstrakcja treści artykułu i normalizacja dokumentów korpusu."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime

from app.textutil import truncate

EXCERPT_CHARS = 1500


@dataclass(frozen=True)
class ExtractedDocument:
    title: str
    text: str
    published_at: datetime | None


def extract_document(html: str | bytes, url: str) -> ExtractedDocument:
    import trafilatura

    doc = trafilatura.bare_extraction(html, url=url, include_comments=False, with_metadata=True)
    text = (getattr(doc, "text", None) or "").strip() if doc else ""
    title = (getattr(doc, "title", None) or "").strip() if doc else ""
    published: datetime | None = None
    raw_date = (getattr(doc, "date", None) or "")[:10] if doc else ""
    try:
        published = datetime.combine(date.fromisoformat(raw_date), datetime.min.time())
    except ValueError:
        published = None
    return ExtractedDocument(title=title, text=text, published_at=published)


def build_excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    return truncate(" ".join(text.split()), limit)


def content_hash(publisher: str, title: str, excerpt: str) -> str:
    return hashlib.sha256(f"{publisher}\n{title}\n{excerpt}".encode()).hexdigest()
