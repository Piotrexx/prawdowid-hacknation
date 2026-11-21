"""Dostęp do korpusu artykułów w PostgreSQL + pgvector.

Korpus jest jedynym źródłem prawdy: ingest zapisuje dokumenty i embeddingi do
tabeli `articles`, a wyszukiwanie korzysta z pgvector. Nie ma równoległego pliku
JSONL ani indeksu w pamięci.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.store.models import ArticleRow, IngestRunRow
from app.textutil import site_domain


@dataclass(frozen=True)
class CorpusDocument:
    doc_id: str
    source_key: str
    publisher: str
    title: str
    excerpt: str
    url: str
    published_at: datetime | None
    similarity: float
    text: str = ""
    retrieved_at: datetime | None = None
    source_type: str = "official"
    tier: int = 1
    license: str = ""
    claim_reviewed: str | None = None
    rating: str | None = None
    appearance_urls: tuple[str, ...] = ()


@dataclass(frozen=True)
class UpsertResult:
    status: str  # created | updated | unchanged
    doc_id: int


@dataclass(frozen=True)
class SourceDocument:
    """Dokument przygotowany przez ingest, przed zapisem do bazy."""

    external_id: str
    source_key: str
    publisher: str
    title: str
    text: str
    excerpt: str
    url: str
    published_at: date | datetime | None
    source_type: str = "official"
    tier: int = 1
    license: str = ""
    storage: str = "excerpt"
    claim_reviewed: str | None = None
    rating: str | None = None
    appearance_urls: tuple[str, ...] = field(default_factory=tuple)


def _as_datetime(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.combine(value, time.min, tzinfo=UTC)


def _content_hash(publisher: str, title: str, text: str) -> str:
    return hashlib.sha256(f"{publisher}\n{title}\n{text}".encode()).hexdigest()


def _passage_count(text: str) -> int:
    return max(1, len(text) // 700 + 1) if text else 0


class CorpusStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def _session(self) -> Session:
        return Session(self._engine, expire_on_commit=False)

    # --- zapis ---

    def get_index_state(self, key: str) -> tuple[str | None, bool]:
        """Zwraca (content_hash, czy_ma_embedding) dla external_id albo URL."""
        with self._session() as db:
            row = db.scalar(select(ArticleRow).where(ArticleRow.external_id == key))
            if row is None:
                row = db.scalar(
                    select(ArticleRow).where(ArticleRow.url == key).order_by(ArticleRow.id.desc())
                )
        if row is None:
            return None, False
        return row.content_hash, row.embedding is not None

    def upsert_document(
        self,
        document: SourceDocument,
        *,
        content_hash: str | None = None,
        embedding: list[float] | None = None,
        embedding_model: str | None = None,
        retrieved_at: datetime | None = None,
    ) -> UpsertResult:
        now = retrieved_at or datetime.now(UTC)
        published = _as_datetime(document.published_at)
        digest = content_hash or _content_hash(document.publisher, document.title, document.text)
        with self._session() as db:
            row = db.scalar(select(ArticleRow).where(ArticleRow.external_id == document.external_id))
            if row is None:
                row = ArticleRow(
                    external_id=document.external_id,
                    source_key=document.source_key,
                    publisher=document.publisher,
                    title=document.title,
                    excerpt=document.excerpt,
                    text=document.text or document.excerpt,
                    source_type=document.source_type,
                    tier=document.tier,
                    license=document.license,
                    storage=document.storage,
                    claim_reviewed=document.claim_reviewed,
                    rating=document.rating,
                    appearance_urls=list(document.appearance_urls),
                    url=document.url,
                    published_at=published,
                    retrieved_at=now,
                    content_hash=digest,
                    embedding=embedding,
                    embedding_model=embedding_model if embedding is not None else None,
                )
                db.add(row)
                db.commit()
                return UpsertResult("created", row.id)

            if row.content_hash == digest:
                if embedding is not None and row.embedding is None:
                    row.embedding = embedding
                    row.embedding_model = embedding_model
                    db.commit()
                    return UpsertResult("updated", row.id)
                return UpsertResult("unchanged", row.id)

            row.source_key = document.source_key
            row.publisher = document.publisher
            row.title = document.title
            row.excerpt = document.excerpt
            row.text = document.text or document.excerpt
            row.source_type = document.source_type
            row.tier = document.tier
            row.license = document.license
            row.storage = document.storage
            row.claim_reviewed = document.claim_reviewed
            row.rating = document.rating
            row.appearance_urls = list(document.appearance_urls)
            row.url = document.url
            row.published_at = published
            row.retrieved_at = now
            row.content_hash = digest
            row.embedding = embedding
            row.embedding_model = embedding_model if embedding is not None else None
            db.commit()
            return UpsertResult("updated", row.id)

    def upsert_article(
        self,
        *,
        source_key: str,
        publisher: str,
        title: str,
        excerpt: str,
        url: str,
        published_at: datetime | date | None,
        content_hash: str,
        embedding: list[float] | None,
        embedding_model: str | None,
        retrieved_at: datetime | None = None,
        external_id: str | None = None,
        text: str | None = None,
        source_type: str = "official",
        tier: int = 1,
        license: str = "",
        storage: str = "excerpt",
        claim_reviewed: str | None = None,
        rating: str | None = None,
        appearance_urls: list[str] | None = None,
    ) -> UpsertResult:
        """Zapis zgodny z wcześniejszym API (używany też w testach)."""
        doc = SourceDocument(
            external_id=external_id
            or f"{source_key}:{hashlib.sha1((url + (claim_reviewed or '')).encode()).hexdigest()[:12]}",
            source_key=source_key,
            publisher=publisher,
            title=title,
            text=text if text is not None else excerpt,
            excerpt=excerpt,
            url=url,
            published_at=published_at,
            source_type=source_type,
            tier=tier,
            license=license,
            storage=storage,
            claim_reviewed=claim_reviewed,
            rating=rating,
            appearance_urls=tuple(appearance_urls or ()),
        )
        return self.upsert_document(
            doc,
            content_hash=content_hash,
            embedding=embedding,
            embedding_model=embedding_model,
            retrieved_at=retrieved_at,
        )

    def delete_source(self, source_key: str) -> int:
        with self._session() as db:
            result = db.execute(delete(ArticleRow).where(ArticleRow.source_key == source_key))
            db.commit()
            return result.rowcount or 0

    # --- odczyt / wyszukiwanie ---

    @staticmethod
    def _to_document(row: ArticleRow, similarity: float = 0.0) -> CorpusDocument:
        return CorpusDocument(
            doc_id=row.external_id,
            source_key=row.source_key,
            publisher=row.publisher,
            title=row.title,
            excerpt=row.excerpt,
            url=row.url,
            published_at=row.published_at,
            similarity=similarity,
            text=row.text or row.excerpt,
            retrieved_at=row.retrieved_at,
            source_type=row.source_type,
            tier=row.tier,
            license=row.license,
            claim_reviewed=row.claim_reviewed,
            rating=row.rating,
            appearance_urls=tuple(row.appearance_urls or ()),
        )

    def search(
        self,
        query_vector: list[float],
        *,
        exclude_url: str | None = None,
        max_age_days: int | None = None,
        limit: int = 20,
    ) -> list[CorpusDocument]:
        distance = ArticleRow.embedding.cosine_distance(query_vector)
        similarity = (1 - distance).label("similarity")
        stmt = select(ArticleRow, similarity).where(ArticleRow.embedding.isnot(None))
        if max_age_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
            stmt = stmt.where((ArticleRow.published_at.is_(None)) | (ArticleRow.published_at >= cutoff))
        if exclude_url:
            stmt = stmt.where(ArticleRow.url != exclude_url)
        stmt = stmt.order_by(distance).limit(limit)
        with self._session() as db:
            rows = db.execute(stmt).all()
        return [self._to_document(row, float(value)) for row, value in rows]

    def load_documents(self) -> list[CorpusDocument]:
        with self._session() as db:
            rows = db.scalars(select(ArticleRow).order_by(ArticleRow.id)).all()
        return [self._to_document(row) for row in rows]

    def all_documents(self) -> list[CorpusDocument]:
        return self.load_documents()

    def factcheck_documents(self) -> list[CorpusDocument]:
        with self._session() as db:
            rows = db.scalars(
                select(ArticleRow).where(ArticleRow.claim_reviewed.isnot(None))
            ).all()
        return [self._to_document(row) for row in rows]

    def find_by_appearance(self, url: str) -> list[CorpusDocument]:
        with self._session() as db:
            rows = db.scalars(
                select(ArticleRow).where(
                    (ArticleRow.url == url) | ArticleRow.appearance_urls.contains([url])
                )
            ).all()
        return [self._to_document(row) for row in rows]

    def count(self) -> int:
        with self._session() as db:
            return db.scalar(select(func.count()).select_from(ArticleRow)) or 0

    def stats(self) -> dict:
        with self._session() as db:
            rows = db.scalars(select(ArticleRow)).all()
        documents = len(rows)
        with_embedding = sum(1 for row in rows if row.embedding is not None)
        by_source: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        domains: set[str] = set()
        version_hash = hashlib.sha256()
        latest: datetime | None = None
        passages = 0
        for row in rows:
            by_source[row.source_key] = by_source.get(row.source_key, 0) + 1
            by_type[row.source_type] = by_type.get(row.source_type, 0) + 1
            by_tier[str(row.tier)] = by_tier.get(str(row.tier), 0) + 1
            domains.add(site_domain(row.url))
            version_hash.update(f"{row.external_id}:{row.content_hash}".encode())
            if row.retrieved_at and (latest is None or row.retrieved_at > latest):
                latest = row.retrieved_at
            passages += _passage_count(row.text or row.excerpt)
        return {
            "documents": documents,
            "passages": passages,
            "domains": len(domains),
            "by_source": by_source,
            "by_type": by_type,
            "by_tier": by_tier,
            "with_embedding": with_embedding,
            "version": version_hash.hexdigest()[:12],
            "built_at": latest,
        }

    def source_summary(self) -> dict[str, dict]:
        with self._session() as db:
            rows = db.execute(
                select(ArticleRow.source_key, func.count(), func.max(ArticleRow.published_at)).group_by(
                    ArticleRow.source_key
                )
            ).all()
        return {
            key: {"documents": count, "newest": newest}
            for key, count, newest in rows
        }

    # --- przebiegi ingestu ---

    def start_ingest_run(self, source_key: str) -> int:
        with self._session() as db:
            row = IngestRunRow(source_key=source_key, started_at=datetime.now(UTC), status="running")
            db.add(row)
            db.commit()
            return row.id

    def finish_ingest_run(
        self,
        run_id: int,
        *,
        fetched: int,
        stored: int,
        errors: int,
        status: str,
        detail: str | None = None,
    ) -> None:
        with self._session() as db:
            db.execute(
                update(IngestRunRow)
                .where(IngestRunRow.id == run_id)
                .values(
                    finished_at=datetime.now(UTC),
                    fetched=fetched,
                    stored=stored,
                    errors=errors,
                    status=status,
                    detail=detail,
                )
            )
            db.commit()

    def recent_ingest_runs(self, limit: int = 20) -> list[dict]:
        with self._session() as db:
            rows = db.scalars(
                select(IngestRunRow).order_by(IngestRunRow.started_at.desc()).limit(limit)
            ).all()
        return [
            {
                "id": row.id,
                "source_key": row.source_key,
                "started_at": row.started_at.isoformat(),
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "fetched": row.fetched,
                "stored": row.stored,
                "errors": row.errors,
                "status": row.status,
                "detail": row.detail,
            }
            for row in rows
        ]
