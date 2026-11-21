"""Dostęp do korpusu artykułów w PostgreSQL + pgvector."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.store.models import ArticleRow, IngestRunRow


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


@dataclass(frozen=True)
class UpsertResult:
    status: str  # created | updated | unchanged
    doc_id: int


class CorpusStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def _session(self) -> Session:
        return Session(self._engine, expire_on_commit=False)

    # --- zapis ---

    def get_content_hash(self, url: str) -> str | None:
        with self._session() as db:
            return db.scalar(select(ArticleRow.content_hash).where(ArticleRow.url == url))

    def get_index_state(self, url: str) -> tuple[str | None, bool]:
        """Zwraca (content_hash, czy_ma_embedding) – pozwala uzupełnić brakujące wektory."""
        with self._session() as db:
            row = db.execute(
                select(ArticleRow.content_hash, ArticleRow.embedding.isnot(None)).where(ArticleRow.url == url)
            ).first()
        if row is None:
            return None, False
        return row[0], bool(row[1])

    def upsert_article(
        self,
        *,
        source_key: str,
        publisher: str,
        title: str,
        excerpt: str,
        url: str,
        published_at: datetime | None,
        content_hash: str,
        embedding: list[float] | None,
        embedding_model: str | None,
        retrieved_at: datetime | None = None,
    ) -> UpsertResult:
        now = retrieved_at or datetime.now(UTC)
        with self._session() as db:
            row = db.scalar(select(ArticleRow).where(ArticleRow.url == url))
            if row is None:
                row = ArticleRow(
                    source_key=source_key,
                    publisher=publisher,
                    title=title,
                    excerpt=excerpt,
                    url=url,
                    published_at=published_at,
                    content_hash=content_hash,
                    embedding=embedding,
                    embedding_model=embedding_model,
                    retrieved_at=now,
                )
                db.add(row)
                db.commit()
                return UpsertResult("created", row.id)

            if row.content_hash == content_hash:
                if embedding is not None and row.embedding is None:
                    row.embedding = embedding
                    row.embedding_model = embedding_model
                    db.commit()
                    return UpsertResult("updated", row.id)
                return UpsertResult("unchanged", row.id)

            row.source_key = source_key
            row.publisher = publisher
            row.title = title
            row.excerpt = excerpt
            row.published_at = published_at
            row.content_hash = content_hash
            row.retrieved_at = now
            row.embedding = embedding
            row.embedding_model = embedding_model if embedding is not None else None
            db.commit()
            return UpsertResult("updated", row.id)

    def delete_source(self, source_key: str) -> int:
        with self._session() as db:
            result = db.execute(delete(ArticleRow).where(ArticleRow.source_key == source_key))
            db.commit()
            return result.rowcount or 0

    # --- odczyt / wyszukiwanie ---

    def search(
        self,
        query_vector: list[float],
        *,
        exclude_url: str | None = None,
        max_age_days: int = 90,
        limit: int = 20,
    ) -> list[CorpusDocument]:
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        distance = ArticleRow.embedding.cosine_distance(query_vector)
        similarity = (1 - distance).label("similarity")
        stmt = (
            select(ArticleRow, similarity)
            .where(ArticleRow.embedding.isnot(None))
            .where((ArticleRow.published_at.is_(None)) | (ArticleRow.published_at >= cutoff))
            .order_by(distance)
            .limit(limit)
        )
        if exclude_url:
            stmt = stmt.where(ArticleRow.url != exclude_url)
        with self._session() as db:
            rows = db.execute(stmt).all()
        return [
            CorpusDocument(
                doc_id=str(row.id),
                source_key=row.source_key,
                publisher=row.publisher,
                title=row.title,
                excerpt=row.excerpt,
                url=row.url,
                published_at=row.published_at,
                similarity=float(similarity_value),
            )
            for row, similarity_value in rows
        ]

    def count(self) -> int:
        with self._session() as db:
            return db.scalar(select(func.count()).select_from(ArticleRow)) or 0

    def stats(self) -> dict:
        with self._session() as db:
            total = db.scalar(select(func.count()).select_from(ArticleRow)) or 0
            with_embedding = (
                db.scalar(select(func.count()).select_from(ArticleRow).where(ArticleRow.embedding.isnot(None)))
                or 0
            )
            by_source = dict(
                db.execute(select(ArticleRow.source_key, func.count()).group_by(ArticleRow.source_key)).all()
            )
            latest = db.scalar(select(func.max(ArticleRow.retrieved_at)))
        return {
            "articles_total": total,
            "with_embedding": with_embedding,
            "by_source": by_source,
            "latest_retrieved_at": latest.isoformat() if latest else None,
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
            rows = db.scalars(select(IngestRunRow).order_by(IngestRunRow.started_at.desc()).limit(limit)).all()
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
