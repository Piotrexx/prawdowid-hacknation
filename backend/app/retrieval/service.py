"""Wyszukiwanie semantyczne artykułów podobnych do sprawdzanej treści."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass

from app.config import Settings
from app.retrieval.corpus import CorpusDocument, CorpusStore
from app.retrieval.embeddings import Embedder

log = logging.getLogger("retrieval")

_TOKEN_RE = re.compile(r"[\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", re.UNICODE)
_STOPWORDS = {
    "oraz", "albo", "tego", "tej", "tym", "jest", "byly", "była", "było", "będzie",
    "dla", "nie", "tak", "ale", "czy", "jako", "przez", "przy", "pod", "nad", "bez",
    "się", "sie", "który", "która", "które", "jego", "jej", "ich", "ten", "ta", "to",
}


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _tokens(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(_normalize(text)) if len(token) > 2]


@dataclass(frozen=True)
class RelatedArticle:
    document: CorpusDocument
    score: float
    keyword_overlap: float


class RetrievalService:
    def __init__(self, settings: Settings, corpus: CorpusStore, embedder: Embedder | None):
        self._settings = settings
        self._corpus = corpus
        self._embedder = embedder

    @property
    def enabled(self) -> bool:
        return self._embedder is not None

    @property
    def model(self) -> str | None:
        return self._embedder.model if self._embedder else None

    @staticmethod
    def build_query(*, keywords: list[str], main_topic: str, summary: str) -> str:
        parts = [main_topic.strip(), "; ".join(keywords), summary.strip()]
        return ". ".join(part for part in parts if part and part.strip(" ;."))

    @staticmethod
    def _keyword_weights(keywords: list[str]) -> dict[str, float]:
        weights: dict[str, float] = {}
        for keyword in keywords:
            raw_tokens = _TOKEN_RE.findall(keyword)
            for token in raw_tokens:
                normalized = _normalize(token)
                if len(normalized) <= 2 or normalized in _STOPWORDS:
                    continue
                # Nazwy własne i liczby są mocniejszym sygnałem „tego samego wydarzenia”.
                is_proper = token[:1].isupper() or token[:1].isdigit()
                weights[normalized] = max(weights.get(normalized, 0.0), 2.0 if is_proper else 1.0)
        return weights

    @classmethod
    def _rerank(
        cls,
        documents: list[CorpusDocument],
        *,
        keywords: list[str],
        min_similarity: float,
        strong_similarity: float,
        max_per_source: int,
        top_k: int,
    ) -> list[RelatedArticle]:
        weights = cls._keyword_weights(keywords)
        total_weight = sum(weights.values()) or 1.0
        scored: list[RelatedArticle] = []
        for document in documents:
            doc_tokens = set(
                _tokens(f"{document.publisher} {document.source_key} {document.title} {document.excerpt}")
            )
            matched = sum(weight for token, weight in weights.items() if token in doc_tokens)
            overlap = matched / total_weight
            score = 0.8 * document.similarity + 0.2 * overlap
            if document.similarity < min_similarity:
                continue
            # Wymagamy albo wspólnego pojęcia, albo wyraźnie wysokiego podobieństwa.
            if overlap <= 0 and document.similarity < strong_similarity:
                continue
            scored.append(RelatedArticle(document=document, score=round(score, 4), keyword_overlap=round(overlap, 4)))

        scored.sort(key=lambda item: item.score, reverse=True)
        chosen: list[RelatedArticle] = []
        per_source: dict[str, int] = {}
        seen_urls: set[str] = set()
        for item in scored:
            if item.document.url in seen_urls:
                continue
            source_count = per_source.get(item.document.source_key, 0)
            if source_count >= max_per_source:
                continue
            chosen.append(item)
            seen_urls.add(item.document.url)
            per_source[item.document.source_key] = source_count + 1
            if len(chosen) >= top_k:
                break
        return chosen

    async def find_related(
        self,
        *,
        keywords: list[str],
        main_topic: str,
        summary: str,
        exclude_url: str | None = None,
    ) -> list[RelatedArticle]:
        if self._embedder is None or not keywords:
            return []
        query = self.build_query(keywords=keywords, main_topic=main_topic, summary=summary)
        if not query:
            return []
        return await asyncio.to_thread(self._find_sync, query, keywords, exclude_url)

    def _find_sync(self, query: str, keywords: list[str], exclude_url: str | None) -> list[RelatedArticle]:
        vector = self._embedder.embed_query(query)  # type: ignore[union-attr]
        documents = self._corpus.search(
            vector,
            exclude_url=exclude_url,
            max_age_days=self._settings.retrieval_max_age_days,
            limit=self._settings.retrieval_candidates,
        )
        return self._rerank(
            documents,
            keywords=keywords,
            min_similarity=self._settings.retrieval_min_similarity,
            strong_similarity=self._settings.retrieval_strong_similarity,
            max_per_source=self._settings.retrieval_max_per_source,
            top_k=self._settings.retrieval_top_k,
        )

    @staticmethod
    def format_context(articles: list[RelatedArticle], limit_chars: int = 600) -> str:
        if not articles:
            return ""
        lines = ["Materiały podobne semantycznie (kontekst, NIE dowód):"]
        for index, article in enumerate(articles, 1):
            document = article.document
            published = document.published_at.strftime("%d.%m.%Y") if document.published_at else "data nieznana"
            lines.append(
                f"\n[{index}] {document.publisher}, {published}, podobieństwo {document.similarity:.2f}\n"
                f"Tytuł: {document.title}\n"
                f"Fragment: {document.excerpt[:limit_chars]}\n"
                f"Link: {document.url}"
            )
        return "\n".join(lines)
