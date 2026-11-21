"""Modele bazy danych: sprawdzenia, zdarzenia bezpieczeństwa i korpus artykułów."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Wymiar musi odpowiadać modelowi embeddingów (EMBEDDING_DIM).
EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    pass


class CheckRow(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    channel: Mapped[str] = mapped_column(String(32))
    session_id: Mapped[str | None] = mapped_column(String(80), index=True)
    cache_key: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"))


class SecurityEventRow(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str] = mapped_column(String(48))
    origin: Mapped[str] = mapped_column(String(48))
    detail: Mapped[str] = mapped_column(String(500))
    check_id: Mapped[str | None] = mapped_column(String(32))


class ArticleRow(Base):
    """Pojedynczy dokument korpusu (tytuł + fragment + link) wraz z embeddingiem."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    publisher: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(160))

    __table_args__ = (
        Index(
            "articles_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("articles_published_at_idx", "published_at"),
    )


class IngestRunRow(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    stored: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="running")
    detail: Mapped[str | None] = mapped_column(Text)
