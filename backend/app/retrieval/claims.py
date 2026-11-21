"""Wyszukiwanie dowodów dla pojedynczego twierdzenia na PostgreSQL + pgvector."""

from __future__ import annotations

import logging
from datetime import date, datetime

from app.config import Settings
from app.retrieval.corpus import CorpusDocument, CorpusStore
from app.retrieval.embeddings import Embedder
from app.retrieval.service import RelatedArticle, RetrievalService
from app.retrieval.types import Hit, Passage, split_passages
from app.schemas import CorpusStats
from app.textutil import tokenize

log = logging.getLogger("retrieval")


class ClaimRetriever:
    """Dostarcza fragmenty źródeł do oceny twierdzeń.

    Ścieżka podstawowa to pgvector + rerank (jak w HEAD). Gdy embeddingi są
    niedostępne, działa uczciwy fallback leksykalny po dokumentach z bazy.
    """

    def __init__(self, settings: Settings, corpus: CorpusStore, embedder: Embedder | None):
        self._settings = settings
        self._corpus = corpus
        self._embedder = embedder
        self._service = RetrievalService(settings, corpus, embedder)

    @property
    def mode(self) -> str:
        if self._corpus.count() == 0:
            return "none"
        return "hybrid" if self._embedder is not None else "bm25"

    @property
    def embedder(self) -> Embedder | None:
        return self._embedder

    @property
    def corpus(self) -> CorpusStore:
        return self._corpus

    @property
    def version(self) -> str:
        return str(self._corpus.stats().get("version", ""))

    @property
    def built_at(self) -> datetime | None:
        value = self._corpus.stats().get("built_at")
        return value if isinstance(value, datetime) else None

    def stats(self) -> CorpusStats:
        raw = self._corpus.stats()
        return CorpusStats(
            documents=int(raw.get("documents", 0)),
            passages=int(raw.get("passages", 0)),
            domains=int(raw.get("domains", 0)),
            by_type=dict(raw.get("by_type", {})),
            version=str(raw.get("version", "")),
            built_at=raw.get("built_at"),
        )

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        if self._embedder is None:
            return None
        return self._embedder.embed_documents(texts)

    def search(self, queries: list[str], k: int, today: date | None = None) -> list[Hit]:
        cleaned = [q.strip() for q in dict.fromkeys(queries) if q and q.strip()]
        if not cleaned:
            return []
        terms = tokenize(" ".join(cleaned))
        documents: dict[str, tuple[CorpusDocument, float]] = {}
        if self._embedder is not None:
            for query in cleaned[:4]:
                try:
                    related: list[RelatedArticle] = self._service._find_sync(query, terms, None)
                except Exception:
                    log.warning("pgvector search nie powiódł się", exc_info=True)
                    related = []
                for item in related:
                    current = documents.get(item.document.doc_id)
                    if current is None or item.score > current[1]:
                        documents[item.document.doc_id] = (item.document, item.score)
        if not documents:
            documents = self._lexical(terms)
        ranked = sorted(documents.values(), key=lambda item: item[1], reverse=True)
        chosen: list[Hit] = []
        per_source: dict[str, int] = {}
        for document, score in ranked:
            if per_source.get(document.source_key, 0) >= self._settings.retrieval_max_per_source:
                continue
            passage = self._best_passage(document, terms)
            chosen.append(Hit(passage=passage, score=round(score, 4)))
            per_source[document.source_key] = per_source.get(document.source_key, 0) + 1
            if len(chosen) >= k:
                break
        return chosen

    def related_materials(self, material: str, k: int = 5) -> list[CorpusDocument]:
        hits = self.search([material[:500]], k)
        seen: dict[str, CorpusDocument] = {}
        for hit in hits:
            seen.setdefault(hit.passage.doc.doc_id, hit.passage.doc)
        return list(seen.values())

    def _lexical(self, terms: list[str]) -> dict[str, tuple[CorpusDocument, float]]:
        if not terms:
            return {}
        term_set = set(terms)
        scored: dict[str, tuple[CorpusDocument, float]] = {}
        for document in self._corpus.all_documents():
            document_terms = set(tokenize(f"{document.title} {document.text or document.excerpt}"))
            if not document_terms:
                continue
            matched = len(term_set & document_terms)
            if not matched:
                continue
            score = matched / len(term_set)
            if score <= 0:
                continue
            scored[document.doc_id] = (document, score)
        return scored

    @staticmethod
    def _best_passage(document: CorpusDocument, terms: list[str]) -> Passage:
        text = document.text or document.excerpt
        passages = split_passages(text) or [text]
        if not terms:
            return Passage(document, passages[0])
        term_set = set(terms)
        best = max(
            passages,
            key=lambda passage: len(term_set & set(tokenize(passage))),
        )
        return Passage(document, best)
