"""Typy wspólne wyszukiwania: dokument, fragment i trafienie."""

from dataclasses import dataclass

from app.retrieval.corpus import CorpusDocument

PASSAGE_CHARS = 700


@dataclass(frozen=True)
class Passage:
    doc: CorpusDocument
    text: str


@dataclass(frozen=True)
class Hit:
    passage: Passage
    score: float


def split_passages(text: str, limit: int = PASSAGE_CHARS) -> list[str]:
    """Dzieli treść na fragmenty zdań o rozsądnej długości."""
    text = (text or "").strip()
    if len(text) <= limit:
        return [text] if text else []
    passages: list[str] = []
    current = ""
    for sentence in _sentences(text):
        if current and len(current) + len(sentence) + 1 > limit:
            passages.append(current)
            current = ""
        current = f"{current} {sentence}".strip()
    if current:
        passages.append(current)
    return passages


def _sentences(text: str) -> list[str]:
    import re

    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
