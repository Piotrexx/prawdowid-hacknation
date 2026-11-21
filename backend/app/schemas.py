"""Publiczny kontrakt API. Frontend i adaptery kanałów zależą wyłącznie od tych modeli."""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


class CheckStatus(StrEnum):
    """Stan obsługi zgłoszenia. Tylko COMPLETED niesie werdykt; pozostałe to nie są werdykty."""

    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    OUT_OF_SCOPE = "out_of_scope"
    ERROR = "error"


class VerdictLabel(StrEnum):
    FAKE = "fake_news"
    REAL = "prawdziwe"
    UNCERTAIN = "niepewne"
    SATIRE = "satyna"
    OPINION = "opinia"


class SourceRef(BaseModel):
    doc_id: str
    title: str
    publisher: str
    url: str
    published_at: date | None = None
    retrieved_at: datetime | None = None
    source_type: str
    source_name: str
    rating: str | None = None
    similarity: float | None = None


class FactCheckResult(BaseModel):
    """Wynik z Google Fact Check Tools API"""
    claim: str
    claimant: str | None = None
    claim_date: str | None = None
    claim_review_url: str
    claim_review_title: str
    publisher_name: str
    publisher_site: str
    rating: str
    textual_rating: str | None = None
    url: str


class KeywordExtraction(BaseModel):
    """Słowa kluczowe wyekstrahowane przez Bielik"""
    keywords: list[str]
    main_topic: str
    summary: str


class CheckMeta(BaseModel):
    duration_ms: int = 0
    stages_ms: dict[str, int] = {}
    provider: str | None = None
    model: str | None = None
    bielik_model: str | None = None
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float | None = None
    processing_location: str = ""
    cached: bool = False
    related_count: int = 0
    embedding_model: str | None = None


class InputInfo(BaseModel):
    kind: Literal["url"]
    text: str = Field(description="Treść artykułu po ekstrakcji")
    url: str
    title: str | None = None


class CheckResponse(BaseModel):
    id: str
    created_at: datetime
    channel: str
    status: CheckStatus
    status_message: str | None = None
    error_code: str | None = None
    input: InputInfo
    verdict: VerdictLabel | None = None
    verdict_label: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    justification: str | None = None
    keywords: list[str] = []
    main_topic: str = ""
    summary: str = ""
    fact_check_results: list[FactCheckResult] = []
    source_articles: list[SourceRef] = []
    related_materials: list[SourceRef] = []
    limitations: list[str] = []
    meta: CheckMeta = CheckMeta()


class CheckRequest(BaseModel):
    url: str = Field(..., max_length=2000)
    session_id: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("Podaj poprawny adres strony (http lub https).")
        return value


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    llm_provider: str
    llm_model: str | None
    bielik_model: str | None
    llm_configured: bool
    bielik_configured: bool
    google_factcheck_configured: bool
    processing_location: str
    retention_days: int
    corpus_ready: bool = False
    corpus_documents: int = 0
    embedding_model: str | None = None
