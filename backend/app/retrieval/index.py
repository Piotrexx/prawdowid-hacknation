"""Indeks korpusu w pamięci: BM25 + (opcjonalnie) embeddingi wielojęzyczne, łączone przez RRF.

Przy kilku tysiącach fragmentów macierz numpy jest szybsza i prostsza w utrzymaniu
niż osobna baza wektorowa; interfejs `CorpusIndex.search` pozwala ją podmienić.
"""

import json
import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit

import numpy as np

from app.catalog import Document
from app.schemas import CorpusStats
from app.textutil import split_sentences, tokenize

log = logging.getLogger("retrieval")

PASSAGE_CHARS = 700
_CANDIDATES_PER_LIST = 30
_RRF_K = 60
_MIN_COSINE = 0.4
_MAX_PASSAGES_PER_DOC = 2


@dataclass(frozen=True)
class Passage:
    doc: Document
    text: str


@dataclass(frozen=True)
class Hit:
    passage: Passage
    score: float


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> np.ndarray: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        self.name = model_name
        self._model = TextEmbedding(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.asarray(list(self._model.embed(texts)), dtype=np.float32)
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True).clip(min=1e-9)


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.size = len(docs)
        lengths = np.array([len(d) for d in docs], dtype=np.float32)
        norm = k1 * (1 - b + b * lengths / max(float(lengths.mean()) if self.size else 1.0, 1.0))
        postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, tokens in enumerate(docs):
            for term, tf in Counter(tokens).items():
                postings[term].append((i, tf))
        # Dla każdego termu od razu liczymy gotowy wkład do wyniku każdego dokumentu.
        self._postings: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for term, entries in postings.items():
            ids = np.array([e[0] for e in entries], dtype=np.int64)
            tfs = np.array([e[1] for e in entries], dtype=np.float32)
            idf = math.log(1 + (self.size - len(entries) + 0.5) / (len(entries) + 0.5))
            self._postings[term] = (ids, idf * tfs * (k1 + 1) / (tfs + norm[ids]))

    def scores(self, query_tokens: list[str]) -> tuple[np.ndarray, np.ndarray]:
        """Zwraca (wynik BM25, liczba różnych termów zapytania trafionych w dokumencie)."""
        scores = np.zeros(self.size, dtype=np.float32)
        matched = np.zeros(self.size, dtype=np.int32)
        for term in set(query_tokens):
            if term in self._postings:
                ids, contribution = self._postings[term]
                scores[ids] += contribution
                matched[ids] += 1
        return scores, matched


def split_passages(doc: Document) -> list[str]:
    if len(doc.text) <= PASSAGE_CHARS:
        return [doc.text]
    passages, current = [], ""
    for paragraph in doc.text.split("\n"):
        for sentence in split_sentences(paragraph):
            if current and len(current) + len(sentence) + 1 > PASSAGE_CHARS:
                passages.append(current)
                current = ""
            current = f"{current} {sentence}".strip()
    if current:
        passages.append(current)
    return passages


def _domain(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


class CorpusIndex:
    def __init__(self, documents: list[Document], version: str = "", built_at: datetime | None = None):
        self.documents = documents
        self.version = version
        self.built_at = built_at
        self.passages = [Passage(doc, text) for doc in documents for text in split_passages(doc)]
        self._bm25 = BM25([tokenize(f"{p.doc.title} {p.text}") for p in self.passages])
        self._embedder: Embedder | None = None
        self._vectors: np.ndarray | None = None

    @classmethod
    def load(cls, corpus_dir: Path) -> "CorpusIndex":
        docs_path, manifest_path = corpus_dir / "documents.jsonl", corpus_dir / "manifest.json"
        documents: list[Document] = []
        if docs_path.exists():
            with docs_path.open(encoding="utf-8") as fh:
                documents = [Document.model_validate_json(line) for line in fh if line.strip()]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        built_at = datetime.fromisoformat(manifest["built_at"]) if manifest.get("built_at") else None
        return cls(documents, manifest.get("version", ""), built_at)

    def attach_embeddings(self, embedder: Embedder, cache_dir: Path) -> None:
        """Wektory liczymy raz na wersję korpusu i model; kolejne starty czytają plik .npy."""
        if not self.passages:
            return
        slug = embedder.name.replace("/", "_")
        cache = cache_dir / f"embeddings-{self.version or 'dev'}-{slug}.npy"
        if cache.exists():
            vectors = np.load(cache)
            if len(vectors) != len(self.passages):
                vectors = None
        else:
            vectors = None
        if vectors is None:
            log.info("liczę embeddingi dla %d fragmentów (jednorazowo)", len(self.passages))
            vectors = embedder.embed([f"{p.doc.title}. {p.text}" for p in self.passages])
            cache_dir.mkdir(parents=True, exist_ok=True)
            np.save(cache, vectors)
        self._embedder, self._vectors = embedder, vectors

    @property
    def mode(self) -> Literal["hybrid", "bm25", "none"]:
        if not self.passages:
            return "none"
        return "hybrid" if self._vectors is not None else "bm25"

    def stats(self) -> CorpusStats:
        return CorpusStats(
            documents=len(self.documents),
            passages=len(self.passages),
            domains=len({_domain(d.url) for d in self.documents}),
            by_type=dict(Counter(d.source_type for d in self.documents)),
            version=self.version,
            built_at=self.built_at,
        )

    def embed(self, texts: list[str]) -> np.ndarray | None:
        return self._embedder.embed(texts) if self._embedder else None

    def search(self, queries: list[str], k: int, today: date | None = None) -> list[Hit]:
        queries = [q for q in dict.fromkeys(q.strip() for q in queries) if q]
        if not queries or not self.passages:
            return []
        today = today or date.today()
        fused: dict[int, float] = defaultdict(float)
        query_vectors = self.embed(queries) if self._vectors is not None else None
        for qi, query in enumerate(queries):
            tokens = tokenize(query)
            scores, matched = self._bm25.scores(tokens)
            # Pojedyncze wspólne słowo to za mało, by uznać fragment za trafny.
            needed = min(2, len(set(tokens)))
            ranked = [i for i in np.argsort(-scores)[:_CANDIDATES_PER_LIST] if scores[i] > 0 and matched[i] >= needed]
            for rank, i in enumerate(ranked):
                fused[int(i)] += 1 / (_RRF_K + rank)
            if query_vectors is not None:
                cosine = self._vectors @ query_vectors[qi]
                for rank, i in enumerate(np.argsort(-cosine)[:_CANDIDATES_PER_LIST]):
                    if cosine[i] < _MIN_COSINE:
                        break
                    fused[int(i)] += 1 / (_RRF_K + rank)

        def recency_boost(doc: Document) -> float:
            if doc.published_at is None:
                return 1.0
            age_years = max((today - doc.published_at).days, 0) / 365
            return 1.0 + 0.15 * max(0.0, 1 - age_years / 2)

        hits: list[Hit] = []
        per_doc: Counter[str] = Counter()
        ranked_all = sorted(fused, key=lambda i: fused[i] * recency_boost(self.passages[i].doc), reverse=True)
        for i in ranked_all:
            passage = self.passages[i]
            if per_doc[passage.doc.id] >= _MAX_PASSAGES_PER_DOC:
                continue
            per_doc[passage.doc.id] += 1
            hits.append(Hit(passage, fused[i]))
            if len(hits) >= k:
                break
        return hits
