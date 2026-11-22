"""Publiczny kontrakt API. Frontend i adaptery kanałów zależą wyłącznie od tych modeli.

Werdykt powstaje w dwóch warstwach:
 * `claims` – ocena każdego twierdzenia osobno, oparta na zweryfikowanych cytatach
   z katalogu źródeł (`evidence`). To warstwa dowodowa i ona jest rozstrzygająca.
 * `verdict` / `confidence` / `fact_check_results` – podsumowanie całego materiału
   oraz dopasowania z Google Fact Check Tools. To warstwa wspierająca.
"""

import datetime as dt
from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


class Verdict(StrEnum):
    CONFIRMED = "potwierdzone"
    FALSE = "falszywe"
    MISLEADING = "wprowadzajace_w_blad"
    INSUFFICIENT = "brak_wystarczajacych_dowodow"
    NOT_VERIFIABLE = "nie_podlega_weryfikacji"


VERDICT_LABELS: dict[Verdict, str] = {
    Verdict.CONFIRMED: "Potwierdzone",
    Verdict.FALSE: "Fałszywe",
    Verdict.MISLEADING: "Wprowadzające w błąd",
    Verdict.INSUFFICIENT: "Brak wystarczających dowodów",
    Verdict.NOT_VERIFIABLE: "Nie podlega weryfikacji",
}

# Alias zachowany dla kanałów, które importowały tę nazwę z wcześniejszej wersji.
VerdictLabel = Verdict


class CheckStatus(StrEnum):
    """Stan obsługi zgłoszenia. Tylko COMPLETED niesie werdykty; pozostałe to nie są werdykty."""

    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    OUT_OF_SCOPE = "out_of_scope"
    ERROR = "error"


SourceType = Literal["official", "legal", "statistics", "international", "factcheck", "media", "reverse_image"]
Stance = Literal["supports", "refutes", "context"]
RetrievalMode = Literal["hybrid", "bm25", "none"]


class SourceRef(BaseModel):
    doc_id: str
    title: str
    publisher: str
    url: str
    published_at: date | None = None
    retrieved_at: datetime | None = None
    source_type: SourceType
    source_name: str
    license: str = ""
    # Tylko dla rekordów fact-checkingowych: twierdzenie sprawdzone przez redakcję i jej ocena.
    claim_reviewed: str | None = None
    rating: str | None = None
    similarity: float | None = None


class Evidence(BaseModel):
    id: str
    stance: Stance
    quote: str = Field(description="Dosłowny fragment źródła, zweryfikowany automatycznie.")
    source: SourceRef
    archival: bool = False


class StrengthFactor(BaseModel):
    code: str
    label: str
    value: str
    effect: Literal["plus", "minus", "neutral"]


class Strength(BaseModel):
    level: Literal["mocna", "umiarkowana", "slaba", "brak"]
    score: float
    factors: list[StrengthFactor] = []


class ClaimResult(BaseModel):
    id: str
    text: str
    verdict: Verdict
    verdict_label: str
    justification: str = Field(description="Interpretacja modelu; fakty są w `evidence`.")
    strength: Strength
    evidence: list[Evidence] = []
    conflict: bool = False
    missing: str | None = None
    risk: Literal["standard", "high"] = "standard"


class Warning(BaseModel):
    code: Literal[
        "injection_detected",
        "archival_material",
        "source_status",
        "incident_match",
        "pii_masked",
        "retrieval_degraded",
        "image_limits",
        "audio_limits",
        "input_truncated",
        "factcheck_unavailable",
        "keywords_degraded",
        "transcription_unavailable",
        "image_manipulation",
        "image_edit_software",
        "ai_generated",
        "ai_edited",
        "content_credentials",
        "image_analysis_unavailable",
    ]
    message: str


class IncidentMatch(BaseModel):
    incident_id: str
    match_type: Literal["url", "domain", "content"]
    title: str
    publisher: str
    url: str
    # `dt.date`, bo nazwa pola przesłania typ `date` w ciele klasy.
    date: dt.date | None = None
    note: str


EventMemberStatus = Literal["accepted", "proposed", "rejected"]
EventLinkStatus = Literal["accepted", "proposed", "rejected"]
EventRelation = Literal[
    "same_event",
    "follow_up",
    "contradiction",
    "related_topic",
    "shared_actor",
    "anchor",
]


class EventAnchor(BaseModel):
    """Publiczny materiał kotwiczący wydarzenie w znanym incydencie z korpusu."""

    incident_id: str
    title: str
    publisher: str = ""
    url: str = ""
    date: dt.date | None = None
    note: str = ""


class EventMemberOut(BaseModel):
    id: int
    event_id: str
    check_id: str
    claim_id: str
    claim_text: str
    verdict: Verdict | None = None
    risk: Literal["standard", "high"] = "standard"
    score: float = 0.0
    reason: str = ""
    status: EventMemberStatus = "accepted"
    source: Literal["auto", "review", "llm", "manual"] = "auto"
    created_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class EventLinkOut(BaseModel):
    id: int
    src_event_id: str
    dst_event_id: str
    relation: EventRelation = "related_topic"
    score: float = 0.0
    reason: str = ""
    evidence: dict[str, str] = {}
    model: str | None = None
    status: EventLinkStatus = "proposed"
    created_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class EventOut(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    title: str
    topic: str = ""
    public_label: str = ""
    summary: str = ""
    status: Literal["active", "merged"] = "active"
    merged_into: str | None = None
    risk: Literal["standard", "high"] = "standard"
    member_count: int = 0
    proposed_count: int = 0
    keywords: list[str] = []
    verdicts: dict[str, int] = {}
    anchors: list[EventAnchor] = []
    first_seen: datetime
    last_seen: datetime


class EventDetailOut(BaseModel):
    event: EventOut
    members: list[EventMemberOut] = []
    links: list[EventLinkOut] = []


class GraphNode(BaseModel):
    id: str
    kind: Literal["event", "anchor"] = "event"
    label: str
    subtitle: str | None = None
    url: str | None = None
    event_id: str | None = None
    risk: Literal["standard", "high"] = "standard"
    member_count: int = 0
    proposed_count: int = 0
    keywords: list[str] = []
    verdicts: dict[str, int] = {}
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: EventRelation = "related_topic"
    score: float | None = None
    status: Literal["accepted", "proposed"] = "accepted"
    reason: str = ""
    model: str | None = None


class EventGraphResponse(BaseModel):
    generated_at: datetime
    window_days: int
    public: bool = False
    min_members: int = 0
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


class EventMemberReview(BaseModel):
    status: Literal["accepted", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class EventLinkReview(BaseModel):
    status: Literal["accepted", "rejected"]
    relation: EventRelation | None = None
    note: str | None = Field(default=None, max_length=1000)


class EventMergeRequest(BaseModel):
    source_event_id: str = Field(min_length=32, max_length=32)


class EventRebuildRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=2000)
    reset: bool = True


class EventRebuildOut(BaseModel):
    processed_checks: int
    events: int
    skipped: int = 0


class ModeratorCaseInfo(BaseModel):
    # "recommended" = tylko zalecenie; "created"/"updated" = sprawa faktycznie jest w kolejce.
    state: Literal["none", "recommended", "created", "updated"] = "none"
    case_id: int | None = None
    occurrences: int | None = None
    notified: bool = False
    message: str = ""


class FactCheckResult(BaseModel):
    """Wynik z Google Fact Check Tools API. Kontekst wspierający, nie dowód z katalogu źródeł."""

    claim: str
    claimant: str | None = None
    claim_date: str | None = None
    claim_review_url: str
    claim_review_title: str
    publisher_name: str
    publisher_site: str
    rating: str
    textual_rating: str | None = None
    url: str | None = None


class KeywordExtraction(BaseModel):
    """Słowa kluczowe i temat wyekstrahowane przez lokalny model (Bielik/Ollama)."""

    keywords: list[str]
    main_topic: str
    # Nieużywane; model lokalny już go nie generuje (każdy token na CPU kosztuje), zostaje dla zgodności.
    summary: str = ""


class ClarifyingQuestion(BaseModel):
    """Pytanie do użytkownika, gdy nie wiadomo, które twierdzenie sprawdzić."""

    text: str
    options: list[str] = Field(default=[], description="Gotowe odpowiedzi do wyboru, jeśli pytanie je ma")


class ClarificationExchange(BaseModel):
    questions: list[str]
    answer: str


class Clarification(BaseModel):
    """Przebieg doprecyzowania. `questions` jest niepuste tylko wtedy, gdy sprawdzenie czeka na odpowiedź."""

    questions: list[ClarifyingQuestion] = []
    missing: list[str] = []
    round: int = 0
    max_rounds: int = 0
    history: list[ClarificationExchange] = []


class InputInfo(BaseModel):
    kind: Literal["text", "url", "image", "audio"]
    text: str = Field(description="Treść po zamaskowaniu danych osobowych.")
    url: str | None = None
    title: str | None = None
    image_metadata: dict[str, str] | None = None
    audio_metadata: dict[str, str] | None = None
    comment: str | None = Field(default=None, description="Komentarz użytkownika do załącznika, po zamaskowaniu.")


class CheckMeta(BaseModel):
    duration_ms: int = 0
    stages_ms: dict[str, int] = {}
    provider: str | None = None
    model: str | None = None
    bielik_model: str | None = None
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    bielik_tokens_in: int = 0
    bielik_tokens_out: int = 0
    cost_usd: float | None = None
    retrieval_mode: RetrievalMode = "none"
    corpus_version: str = ""
    processing_location: str = ""
    cached: bool = False
    related_count: int = 0
    embedding_model: str | None = None


class EngineStatus(BaseModel):
    engine: str
    ok: bool
    results: int = 0
    error: str | None = None


class ImageMatch(BaseModel):
    """Kopia zdjęcia znaleziona w sieci i jej relacja do przesłanej wersji."""
    engine: str
    page_url: str
    image_url: str | None = None
    thumbnail_url: str | None = None
    title: str | None = None
    domain: str | None = None
    first_seen: date | None = None
    relation: Literal["identical", "locally_modified", "different_version", "not_comparable", "not_downloaded"]
    difference: float | None = None


class ImageRegion(BaseModel):
    """Obszar zdjęcia (współrzędne 0–1), który różni się od większości kopii."""
    x: float
    y: float
    width: float
    height: float


class AiSignal(BaseModel):
    """Ślad generowania przez AI zapisany w pliku."""
    source: Literal["c2pa", "iptc", "generator_metadata"]
    kind: Literal["ai_generated", "ai_edited"]
    detail: str
    generator: str | None = None
    signed: bool = Field(default=False, description="Podpis C2PA nienaruszony")


class AiAssessment(BaseModel):
    result: Literal["ai_generated", "ai_edited", "predates_generative_ai", "no_signals"]
    signals: list[AiSignal] = []
    content_credentials: str | None = Field(default=None, description="Podsumowanie manifestu C2PA, jeśli plik go ma")


class ImageAnalysis(BaseModel):
    assessment: Literal["manipulation_suspected", "consistent_with_copies", "insufficient_copies", "no_matches"]
    sha256: str
    width: int
    height: int
    engines: list[EngineStatus] = []
    matches_found: int = 0
    compared: int = 0
    identical: int = 0
    locally_modified: int = 0
    different_versions: int = 0
    earliest_seen: date | None = None
    changed_regions: list[ImageRegion] = []
    exif: dict[str, str] = {}
    ai: AiAssessment | None = None
    matches: list[ImageMatch] = []


class CheckResponse(BaseModel):
    id: str
    created_at: datetime
    channel: str
    status: CheckStatus
    # Komunikat dla statusów innych niż COMPLETED (prosty język, po polsku).
    status_message: str | None = None
    error_code: str | None = None
    input: InputInfo
    summary: str | None = None
    # --- warstwa dowodowa (rozstrzygająca) ---
    claims: list[ClaimResult] = []
    warnings: list[Warning] = []
    incident_matches: list[IncidentMatch] = []
    # Materiały znalezione, gdy ocena nie mogła zostać wykonana (np. awaria modelu).
    related_materials: list[SourceRef] = []
    moderator_case: ModeratorCaseInfo = ModeratorCaseInfo()
    # --- warstwa wspierająca (podsumowanie całego materiału + fact-checki zewnętrzne) ---
    verdict: Verdict | None = None
    verdict_label: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    justification: str | None = None
    keywords: list[str] = []
    main_topic: str = ""
    fact_check_results: list[FactCheckResult] = []
    source_articles: list[SourceRef] = Field(
        default=[],
        description=(
            "Źródła, na których oparto odpowiedź (bez powtórzeń), zapisywane razem z pytaniem, "
            "czasem i wynikiem, aby przebieg sprawdzenia był pełny."
        ),
    )
    limitations: list[str] = []
    # Wynik osobnej analizy zdjęcia (odwrotne wyszukiwanie, porównanie kopii, ślady AI).
    image_analysis: ImageAnalysis | None = None
    # Sprawdzenie, na którego pytanie doprecyzowujące odpowiada to zgłoszenie.
    parent_check_id: str | None = None
    clarification: Clarification | None = None
    meta: CheckMeta = CheckMeta()
    request_count: int = 1


class CheckRequest(BaseModel):
    """Nowe sprawdzenie (`text` albo `url`) lub odpowiedź na pytanie doprecyzowujące (`parent_check_id` + `text`)."""

    text: str | None = Field(default=None, max_length=20000)
    url: str | None = Field(default=None, max_length=2000)
    parent_check_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    session_id: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("Podaj poprawny adres strony (http lub https).")
        return value

    @model_validator(mode="after")
    def _require_input(self) -> "CheckRequest":
        if self.parent_check_id:
            if not (self.text and self.text.strip()) or self.url:
                raise ValueError("Odpowiedź na pytanie musi być tekstem.")
        elif self.text is None and not self.url:
            raise ValueError("Podaj treść wiadomości albo adres strony.")
        return self


class ConsentRequest(BaseModel):
    """Zgoda na politykę prywatności. Zapisujemy sam fakt zgody, bez treści sprawdzeń.

    `session_id` może być pominięty – wtedy backend bierze go z ciasteczka sesji.
    """

    session_id: str | None = Field(
        default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )
    policy_version: str = Field(max_length=32)
    accepted: bool = True


class ConsentResponse(BaseModel):
    session_id: str
    policy_version: str
    accepted: bool
    recorded_at: datetime


class CorpusStats(BaseModel):
    documents: int
    passages: int
    domains: int
    by_type: dict[str, int]
    version: str
    built_at: datetime | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    llm_provider: str
    llm_model: str | None
    bielik_model: str | None
    llm_configured: bool
    bielik_configured: bool
    google_factcheck_configured: bool
    retrieval_mode: RetrievalMode
    corpus: CorpusStats
    processing_location: str
    retention_days: int
    corpus_ready: bool = False
    corpus_documents: int = 0
    embedding_model: str | None = None


class CaseOut(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    claim_text: str
    status: Literal["open", "in_review", "resolved"]
    risk: Literal["standard", "high"]
    occurrences: int
    channels: list[str]
    notified_at: datetime | None
    note: str
    check_ids: list[str]
    comments_count: int = 0


class CaseUpdate(BaseModel):
    status: Literal["open", "in_review", "resolved"] | None = None
    note: str | None = Field(default=None, max_length=2000)
    # Każdy moderator może poprawić treść sprawy i jej wagę.
    claim_text: str | None = Field(default=None, min_length=1, max_length=20000)
    risk: Literal["standard", "high"] | None = None


class SecurityEventOut(BaseModel):
    id: int
    created_at: datetime
    kind: str
    origin: str
    detail: str
    check_id: str | None


class CheckListItem(BaseModel):
    id: str
    created_at: datetime
    channel: str
    status: CheckStatus
    input_kind: str
    input_preview: str
    verdicts: list[Verdict]
    duration_ms: int
    cost_usd: float | None
    keywords: list[str] = []
    factcheck_count: int = 0


class MetricsResponse(BaseModel):
    checks_total: int
    by_status: dict[str, int]
    by_channel: dict[str, int]
    by_verdict: dict[str, int]
    abstention_rate: float | None
    median_duration_ms: int | None
    p95_duration_ms: int | None
    tokens_in: int
    tokens_out: int
    cost_usd_total: float | None
    cost_usd_per_1000: float | None
    errors: dict[str, int]
    security_events: dict[str, int]
    open_cases: int
    avg_factchecks: float = 0.0
    consents: int = 0


class ArchiveRequest(BaseModel):
    """Prośba o kontrolowaną archiwizację materiału wskazanego przez użytkownika."""

    check_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    session_id: str | None = Field(
        default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )


class ArchiveOut(BaseModel):
    id: str
    check_id: str | None
    created_at: datetime
    retention_until: datetime
    url: str | None = None
    title: str | None = None
    excerpt: str
    content_hash: str
    legal_basis: str


# --- Konta moderatorów, komentarze, audyt i ustawienia modelu ---

ModeratorRole = Literal["moderator", "superuser"]


class ModeratorOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: ModeratorRole
    is_active: bool
    created_at: datetime
    created_by: str | None = None
    last_login_at: datetime | None = None
    must_change_password: bool = False
    notify_discord: bool = False
    notify_email: bool = False
    notify_push: bool = False
    discord_webhook_url: str | None = None
    comment_notify_threshold: int = 2


class ModeratorLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class ModeratorLoginOut(BaseModel):
    token: str
    expires_at: datetime
    moderator: ModeratorOut


class ModeratorCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(default="", max_length=120)
    role: ModeratorRole = "moderator"
    # Puste pole = hasło startowe wygenerowane przez serwer.
    password: str | None = Field(default=None, max_length=1024)
    must_change_password: bool = True


class ModeratorCreatedOut(BaseModel):
    moderator: ModeratorOut
    generated_password: str | None = None


class ModeratorUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    role: ModeratorRole | None = None
    is_active: bool | None = None
    must_change_password: bool | None = None


class ModeratorPasswordResetOut(BaseModel):
    moderator: ModeratorOut
    generated_password: str


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    notify_discord: bool | None = None
    notify_email: bool | None = None
    notify_push: bool | None = None
    discord_webhook_url: str | None = Field(default=None, max_length=500)
    comment_notify_threshold: int | None = Field(default=None, ge=1, le=20)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=10, max_length=1024)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class CommentOut(BaseModel):
    id: int
    case_id: int | None = None
    article_id: int | None = None
    moderator_id: int | None = None
    author_email: str
    author_name: str
    body: str
    created_at: datetime
    edited_at: datetime | None = None
    case_claim_preview: str | None = None
    article_title: str | None = None


class ActionOut(BaseModel):
    id: int
    action: str
    field: str | None = None
    value_before: str | None = None
    value_after: str | None = None
    detail: str | None = None
    case_id: int | None = None
    article_id: int | None = None
    case_claim_preview: str | None = None
    created_at: datetime


class ProfileStats(BaseModel):
    comments: int = 0
    status_changes: int = 0
    edits: int = 0
    cases_touched: int = 0


class ProfileOut(BaseModel):
    moderator: ModeratorOut
    stats: ProfileStats
    comments: list[CommentOut] = []
    actions: list[ActionOut] = []
    email_available: bool = False
    push_available: bool = False
    discord_available: bool = False


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=5, max_length=80)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)
    keys: PushKeys
    user_agent: str | None = Field(default=None, max_length=200)


class PushPublicKeyOut(BaseModel):
    public_key: str
    configured: bool = False


class LlmModelOut(BaseModel):
    id: str
    label: str
    price_input: float | None = None
    price_output: float | None = None


class LlmProviderOut(BaseModel):
    key: str
    name: str
    icon: str | None = None
    base_url: str
    requires_key: bool
    is_local: bool = False
    note: str = ""
    models: list[LlmModelOut] = []


class LlmSettingsOut(BaseModel):
    provider: str
    model: str
    base_url: str
    json_mode: str
    price_input: float | None = None
    price_output: float | None = None
    api_key_set: bool = False
    api_key_source: Literal["panel", "env", "none"] = "none"
    api_key_hint: str | None = None
    requires_key: bool = True
    is_local: bool = False
    configured: bool = False


class LlmSettingsUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=32)
    model: str = Field(min_length=1, max_length=160)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    price_input: float | None = Field(default=None, ge=0)
    price_output: float | None = Field(default=None, ge=0)
    json_mode: Literal["json_object", "json_schema"] | None = None
    # `true` usuwa klucz zapisany w panelu i wraca do klucza z .env.
    clear_api_key: bool = False
