"""Embeddingi tekstu: lokalny fastembed (multilingual-e5) albo deterministyczny fake do testów."""

from __future__ import annotations

import hashlib
import logging
import math
import threading
from typing import Protocol

from app.config import Settings

log = logging.getLogger("embeddings")


class Embedder(Protocol):
    model: str
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]


class FastEmbedEmbedder:
    """Leniwie ładowany model fastembed. Pierwsze użycie pobiera ok. 470 MB wag."""

    def __init__(self, model: str, dim: int, cache_dir: str | None = None):
        from fastembed import TextEmbedding

        supported = {entry["model"] for entry in TextEmbedding.list_supported_models()}
        if model not in supported:
            raise ValueError(f"Model {model} nie jest obsługiwany przez fastembed w tej wersji.")
        self.model = model
        self.dim = dim
        self._cache_dir = cache_dir
        self._model = None
        self._lock = threading.Lock()
        self._uses_e5_prefix = "e5" in model.lower()

    def _ensure_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding

                    log.info("Ładuję model embeddingów %s", self.model)
                    self._model = TextEmbedding(model_name=self.model, cache_dir=self._cache_dir)
        return self._model

    def _embed(self, texts: list[str], prefix: str) -> list[list[float]]:
        if not texts:
            return []
        prepared = [f"{prefix}{text}" for text in texts] if self._uses_e5_prefix else texts
        model = self._ensure_model()
        vectors = [list(map(float, vector)) for vector in model.embed(prepared)]
        for vector in vectors:
            if len(vector) != self.dim:
                raise ValueError(
                    f"Model {self.model} zwrócił wektor o wymiarze {len(vector)}, oczekiwano {self.dim}."
                )
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "passage: ")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query: ")[0]


class FakeEmbedder:
    """Deterministyczne embeddingi do testów – bez pobierania modelu i bez sieci."""

    def __init__(self, dim: int = 384, model: str = "fake-e5-small", mapping: dict[str, list[float]] | None = None):
        self.dim = dim
        self.model = model
        self._mapping = mapping or {}
        self._default = _normalize(self._hash_vector("domyślny tekst"))

    def _hash_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [((byte / 255.0) * 2.0 - 1.0) for byte in digest]
        while len(values) < self.dim:
            digest = hashlib.sha256(digest).digest()
            values.extend(((byte / 255.0) * 2.0 - 1.0) for byte in digest)
        return values[: self.dim]

    def _vector(self, text: str) -> list[float]:
        if text in self._mapping:
            return self._mapping[text]
        # Pozwala dopasować zapytanie po fragmencie (np. temat + keywordy).
        for key, vector in self._mapping.items():
            if key and key in text:
                return vector
        return self._default

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def build_embedder(settings: Settings) -> Embedder | None:
    if settings.embedding_backend == "none":
        return None
    from app.store.models import EMBEDDING_DIM

    if settings.embedding_dim != EMBEDDING_DIM:
        raise ValueError(
            f"EMBEDDING_DIM={settings.embedding_dim} nie zgadza się z vector({EMBEDDING_DIM}) w bazie."
        )
    try:
        return FastEmbedEmbedder(
            model=settings.embedding_model,
            dim=settings.embedding_dim,
            cache_dir=settings.embedding_cache_dir,
        )
    except Exception:
        log.exception("Nie udało się skonfigurować modelu embeddingów")
        return None
