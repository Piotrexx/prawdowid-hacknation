"""Modele bazy danych: sprawdzenia, sprawy moderatora, zgody, archiwum, korpus."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Wymiar musi odpowiadać modelowi embeddingów (EMBEDDING_DIM).
EMBEDDING_DIM = 384


def _json() -> JSON:
    """JSONB na PostgreSQL, zwykły JSON gdzie indziej (np. w testach)."""
    return JSON().with_variant(JSONB, "postgresql")


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
    result: Mapped[dict] = mapped_column(_json())


class SecurityEventRow(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str] = mapped_column(String(48))
    origin: Mapped[str] = mapped_column(String(48))
    detail: Mapped[str] = mapped_column(String(500))
    check_id: Mapped[str | None] = mapped_column(String(32), index=True)


class CaseRow(Base):
    """Nierozstrzygnięte zgłoszenie przekazane do kolejki moderatora."""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    claim_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    risk: Mapped[str] = mapped_column(String(16), default="standard")
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    channels: Mapped[list] = mapped_column(_json(), default=list)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(Text, default="")
    links: Mapped[list["CaseLinkRow"]] = relationship(cascade="all, delete-orphan")


class CaseLinkRow(Base):
    __tablename__ = "case_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    check_id: Mapped[str] = mapped_column(String(32), index=True)


class ConsentRow(Base):
    """Zgoda na politykę prywatności. Trzymamy sam fakt zgody i jej wersję –
    bez treści sprawdzeń i bez odpowiedzi modelu."""

    __tablename__ = "privacy_consents"

    session_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    policy_version: Mapped[str] = mapped_column(String(32), primary_key=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ArchivedMaterialRow(Base):
    """Kontrolowana archiwizacja materiału wskazanego przez użytkownika.

    Nie przechowujemy pełnych treści ani obrazów – tylko krótki fragment, skrót
    i metadane potrzebne do audytu, z jawnym terminem retencji.
    """

    __tablename__ = "archived_materials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    check_id: Mapped[str | None] = mapped_column(String(32), index=True)
    session_id: Mapped[str | None] = mapped_column(String(80), index=True)
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    legal_basis: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ArticleRow(Base):
    """Pojedynczy dokument korpusu wraz z metadanymi źródła i embeddingiem."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    url: Mapped[str] = mapped_column(Text, index=True)
    publisher: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(24), default="official")
    tier: Mapped[int] = mapped_column(Integer, default=1)
    license: Mapped[str] = mapped_column(Text, default="")
    storage: Mapped[str] = mapped_column(String(16), default="excerpt")
    claim_reviewed: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[str | None] = mapped_column(String(160))
    appearance_urls: Mapped[list] = mapped_column(_json(), default=list)
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
