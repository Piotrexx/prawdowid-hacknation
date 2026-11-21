"""Publiczny kontrakt API. Frontend i adaptery kanałów zależą wyłącznie od tych modeli."""

import datetime as dt
from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


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


class CheckStatus(StrEnum):
    """Stan obsługi zgłoszenia. Tylko COMPLETED niesie werdykty; pozostałe to nie są werdykty."""

    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    OUT_OF_SCOPE = "out_of_scope"
    ERROR = "error"


SourceType = Literal["official", "legal", "statistics", "international", "factcheck", "media"]
Stance = Literal["supports", "refutes", "context"]


class SourceRef(BaseModel):
    doc_id: str
    title: str
    publisher: str
    url: str
    published_at: date | None = None
    retrieved_at: datetime | None = None
    source_type: SourceType
    source_name: str
    language: str = "pl"
    license: str = ""
    # Tylko dla rekordów fact-checkingowych: twierdzenie sprawdzone przez redakcję i jej ocena.
    claim_reviewed: str | None = None
    rating: str | None = None


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
        "input_truncated",
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


class ModeratorCaseInfo(BaseModel):
    # "recommended" = tylko zalecenie; "created"/"updated" = sprawa faktycznie jest w kolejce.
    state: Literal["none", "recommended", "created", "updated"] = "none"
    case_id: int | None = None
    occurrences: int | None = None
    notified: bool = False
    message: str = ""


class InputInfo(BaseModel):
    kind: Literal["text", "url", "image"]
    text: str = Field(description="Treść po zamaskowaniu danych osobowych.")
    url: str | None = None
    title: str | None = None
    image_metadata: dict[str, str] | None = None


class CheckMeta(BaseModel):
    duration_ms: int = 0
    stages_ms: dict[str, int] = {}
    provider: str | None = None
    model: str | None = None
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float | None = None
    retrieval_mode: Literal["hybrid", "bm25", "none"] = "none"
    corpus_version: str = ""
    processing_location: str = ""
    cached: bool = False


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
    claims: list[ClaimResult] = []
    warnings: list[Warning] = []
    incident_matches: list[IncidentMatch] = []
    # Materiały znalezione, gdy ocena nie mogła zostać wykonana (np. awaria modelu).
    related_materials: list[SourceRef] = []
    moderator_case: ModeratorCaseInfo = ModeratorCaseInfo()
    limitations: list[str] = []
    meta: CheckMeta = CheckMeta()


class CheckRequest(BaseModel):
    text: str | None = Field(default=None, max_length=20000)
    url: str | None = Field(default=None, max_length=2000)
    session_id: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class SourceCatalogEntry(BaseModel):
    id: str
    name: str
    publisher: str
    homepage: str
    source_type: SourceType
    tier: int
    language: str
    license: str
    storage: Literal["full_text", "excerpt", "structured"]
    qualification: str
    update_policy: str
    enabled: bool
    disabled_reason: str | None = None
    documents: int = 0
    newest: date | None = None


class CorpusStats(BaseModel):
    documents: int
    passages: int
    domains: int
    by_type: dict[str, int]
    version: str
    built_at: datetime | None = None


class SourcesResponse(BaseModel):
    sources: list[SourceCatalogEntry]
    corpus: CorpusStats
    rules: list[str]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    llm_provider: str
    llm_model: str | None
    llm_configured: bool
    retrieval_mode: Literal["hybrid", "bm25", "none"]
    corpus: CorpusStats
    processing_location: str
    retention_days: int


class SmsInbound(BaseModel):
    phone: str = Field(min_length=3, max_length=64)
    text: str = Field(max_length=4000)


class SmsMessage(BaseModel):
    id: int
    direction: Literal["in", "out"]
    body: str
    created_at: datetime
    check_id: str | None = None


class SmsThread(BaseModel):
    messages: list[SmsMessage]


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


class CaseUpdate(BaseModel):
    status: Literal["open", "in_review", "resolved"] | None = None
    note: str | None = Field(default=None, max_length=2000)


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
