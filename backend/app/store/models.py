"""Modele bazy danych: sprawdzenia, sprawy moderatora, zgody, archiwum, korpus."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    comments: Mapped[list["CaseCommentRow"]] = relationship(
        cascade="all, delete-orphan", order_by="CaseCommentRow.created_at"
    )


class CaseLinkRow(Base):
    __tablename__ = "case_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    check_id: Mapped[str] = mapped_column(String(32), index=True)


class EventRow(Base):
    """Wydarzenie: klaster zgłoszeń i twierdzeń dotyczących tej samej sytuacji.

    To warstwa kontekstu analitycznego. Przynależność do wydarzenia nigdy nie
    przesądza o prawdziwości twierdzenia – werdykt powstaje wyłącznie z cytatów
    w `claims`.
    """

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    title: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(Text, default="")
    # Etykieta bezpieczna dla mapy publicznej: temat lub słowa kluczowe,
    # nigdy pełna treść zgłoszenia użytkownika.
    public_label: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    merged_into: Mapped[str | None] = mapped_column(String(32), index=True)
    risk: Mapped[str] = mapped_column(String(16), default="standard")
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    proposed_count: Mapped[int] = mapped_column(Integer, default=0)
    keywords: Mapped[list] = mapped_column(_json(), default=list)
    verdicts: Mapped[dict] = mapped_column(_json(), default=dict)
    # Kotwice: publiczne metadane znanych incydentów (fact-checki z korpusu).
    anchors: Mapped[list] = mapped_column(_json(), default=list)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(160))

    members: Mapped[list["EventMemberRow"]] = relationship(
        cascade="all, delete-orphan", order_by="EventMemberRow.created_at"
    )

    __table_args__ = (
        Index(
            "events_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class EventMemberRow(Base):
    """Jedno twierdzenie z jednego zgłoszenia przypisane do wydarzenia.

    `status="proposed"` oznacza kandydata do akceptacji przez moderatora;
    tylko `accepted` liczy się do mapy i statystyk wydarzenia.
    """

    __tablename__ = "event_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    check_id: Mapped[str] = mapped_column(
        ForeignKey("checks.id", ondelete="CASCADE"), index=True
    )
    claim_id: Mapped[str] = mapped_column(String(64), index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str | None] = mapped_column(String(32))
    risk: Mapped[str] = mapped_column(String(16), default="standard")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="accepted", index=True)
    source: Mapped[str] = mapped_column(String(16), default="auto")
    # Słowa kluczowe, temat i kotwice tego konkretnego zgłoszenia. Wydarzenie
    # przelicza je po usunięciu zgłoszenia, więc treść użytkownika nie zostaje
    # w agregacie po wygaśnięciu retencji.
    keywords: Mapped[list] = mapped_column(_json(), default=list)
    anchors: Mapped[list] = mapped_column(_json(), default=list)
    topic: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(254))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("event_id", "check_id", "claim_id", name="event_members_unique"),
    )


class EventLinkRow(Base):
    """Relacja między dwoma wydarzeniami, z jawnym uzasadnieniem i statusem akceptacji."""

    __tablename__ = "event_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    src_event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    dst_event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    # Relacja powstała z konkretnego zgłoszenia; jego usunięcie usuwa też link,
    # bo uzasadnienie i cytaty mogą zawierać treść użytkownika.
    origin_check_id: Mapped[str | None] = mapped_column(
        ForeignKey("checks.id", ondelete="CASCADE"), index=True
    )
    relation: Mapped[str] = mapped_column(String(32), default="related_topic")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(_json(), default=dict)
    model: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), default="proposed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(254))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("src_event_id", "dst_event_id", "relation", name="event_links_unique"),
    )


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


class ModeratorRow(Base):
    """Konto moderatora: logowanie e-mailem i hasłem oraz własne ustawienia powiadomień."""

    __tablename__ = "moderators"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    # „superuser” może zakładać i wyłączać konta oraz zmieniać model językowy.
    role: Mapped[str] = mapped_column(String(16), default="moderator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_by: Mapped[str | None] = mapped_column(String(254))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- ustawienia powiadomień (każdy kanał osobno, domyślnie wyłączone) ---
    notify_discord: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_push: Mapped[bool] = mapped_column(Boolean, default=False)
    # Prywatny webhook Discorda; bez niego używany jest wspólny z konfiguracji.
    discord_webhook_url: Mapped[str | None] = mapped_column(Text)
    # Po ilu komentarzach do jednej sprawy wysłać powiadomienie.
    comment_notify_threshold: Mapped[int] = mapped_column(Integer, default=2)


class ModeratorSessionRow(Base):
    """Aktywna sesja panelu. Token jest trzymany wyłącznie jako skrót SHA-256."""

    __tablename__ = "moderator_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    moderator_id: Mapped[int] = mapped_column(
        ForeignKey("moderators.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(200))


class CaseCommentRow(Base):
    """Opinia moderatora o sprawie albo o artykule z korpusu.

    `author_email` i `author_name` są kopią na moment zapisu – komentarz zostaje
    czytelny także po wyłączeniu albo usunięciu konta autora.
    """

    __tablename__ = "case_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int | None] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    moderator_id: Mapped[int | None] = mapped_column(
        ForeignKey("moderators.id", ondelete="SET NULL"), index=True
    )
    author_email: Mapped[str] = mapped_column(String(254))
    author_name: Mapped[str] = mapped_column(String(120), default="")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("case_comments_target_idx", "case_id", "article_id"),)


class ModeratorActionRow(Base):
    """Ślad audytowy: kto, kiedy i co zmienił w sprawie."""

    __tablename__ = "moderator_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    moderator_id: Mapped[int | None] = mapped_column(
        ForeignKey("moderators.id", ondelete="SET NULL"), index=True
    )
    author_email: Mapped[str] = mapped_column(String(254), index=True)
    author_name: Mapped[str] = mapped_column(String(120), default="")
    case_id: Mapped[int | None] = mapped_column(Integer, index=True)
    article_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # status_change | edit | comment | comment_deleted | note | llm_change | account
    action: Mapped[str] = mapped_column(String(32), index=True)
    field: Mapped[str | None] = mapped_column(String(48))
    value_before: Mapped[str | None] = mapped_column(Text)
    value_after: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PushSubscriptionRow(Base):
    """Subskrypcja Web Push przeglądarki moderatora (RFC 8030/8291)."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    moderator_id: Mapped[int] = mapped_column(
        ForeignKey("moderators.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(80))
    user_agent: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AppSettingRow(Base):
    """Ustawienia zmieniane w panelu (np. wybrany model językowy).

    Konfiguracja z `.env` jest wartością domyślną; wpis w tej tabeli ją nadpisuje.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(_json(), default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str | None] = mapped_column(String(254))
