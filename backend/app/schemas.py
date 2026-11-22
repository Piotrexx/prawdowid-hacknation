"""Publiczny kontrakt API. Frontend i adaptery kanałów zależą wyłącznie od tych modeli."""

import datetime as dt
from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


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


class ClarifyingQuestion(BaseModel):
    """Pytanie do użytkownika, gdy nie wiadomo, co dokładnie sprawdzić."""
    text: str
    options: list[str] = Field(default=[], description="Gotowe odpowiedzi do wyboru, jeśli pytanie je ma")


class KeywordExtraction(BaseModel):
    """Słowa kluczowe wyekstrahowane przez Bielik"""
    keywords: list[str]
    main_topic: str
    summary: str


class ClarityCheck(BaseModel):
    """Czy wiadomo, które twierdzenie sprawdzić; jeśli nie – pytania do użytkownika."""
    missing: list[str] = []
    needs_clarification: bool = False
    questions: list[ClarifyingQuestion] = []


class ClarificationExchange(BaseModel):
    questions: list[str]
    answer: str


class Clarification(BaseModel):
    """Przebieg doprecyzowania. `questions` jest niepuste tylko przy statusie needs_clarification."""
    questions: list[ClarifyingQuestion] = []
    missing: list[str] = []
    round: int = 0
    max_rounds: int = 0
    history: list[ClarificationExchange] = []


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


class InputInfo(BaseModel):
    kind: Literal["url", "text", "image"]
    text: str = Field(description="Treść artykułu po ekstrakcji lub tekst wklejony przez użytkownika")
    url: str
    title: str | None = None


class CheckWarning(BaseModel):
    code: str
    message: str


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
    status_message: str | None = None
    error_code: str | None = None
    input: InputInfo
    verdict: VerdictLabel | None = None
    verdict_label: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    justification: str | None = None
    keywords: list[str] = []
    main_topic: str = ""
    fact_check_results: list[FactCheckResult] = []
    source_articles: list[SourceRef] = []
    limitations: list[str] = []
    warnings: list[CheckWarning] = []
    image_analysis: ImageAnalysis | None = None
    parent_check_id: str | None = None
    clarification: Clarification | None = None
    meta: CheckMeta = CheckMeta()


class CheckRequest(BaseModel):
    """Nowe sprawdzenie (`url` albo `text`) lub odpowiedź na pytanie doprecyzowujące (`parent_check_id` + `text`)."""

    url: str | None = Field(default=None, max_length=2000)
    text: str | None = Field(default=None, max_length=20_000)
    parent_check_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    session_id: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @model_validator(mode="after")
    def _one_input(self) -> "CheckRequest":
        has_url = bool(self.url and self.url.strip())
        has_text = bool(self.text and self.text.strip())
        if self.parent_check_id:
            if not has_text or has_url:
                raise ValueError("Odpowiedź na pytanie musi zawierać tekst (bez linku w polu url).")
        elif has_url == has_text:
            raise ValueError("Podaj link albo tekst do sprawdzenia.")
        return self


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