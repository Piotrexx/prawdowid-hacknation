"""Testy używają podstawionego modelu i małego, wymyślonego korpusu (domena example.org).
Prawdziwy korpus i prawdziwy model sprawdza `eval/run_eval.py`."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.catalog import Document
from app.config import Settings
from app.core.prompts import (
    ClaimAssessment,
    ExtractedClaim,
    Extraction,
    ImageReading,
    PassageJudgement,
)
from app.llm.base import LLMError, Usage
from app.main import build_state, create_app
from app.retrieval.index import CorpusIndex
from app.schemas import Verdict

ADMIN = {"X-Admin-Token": "test-token"}
TODAY = date.today()


def make_doc(doc_id: str, text: str, *, source_type="official", tier=1, age_days=10, publisher="Urząd Testowy", **extra) -> Document:
    return Document(
        id=doc_id,
        source_id=f"test-{source_type}",
        title=f"Dokument {doc_id}",
        publisher=publisher,
        url=f"https://example.org/{doc_id}",
        source_type=source_type,
        tier=tier,
        license="fikstura testowa",
        published_at=TODAY - timedelta(days=age_days),
        retrieved_at=datetime.now(UTC),
        text=text,
        **extra,
    )


VACCINE_QUOTE = "Program szczepień ochronnych w Testowie rozpoczął się 1 marca."
BRIDGE_QUOTE = "Most został zamknięty na czas remontu i nie uległ zniszczeniu."
DOCS = [
    make_doc("szczepienia", f"{VACCINE_QUOTE} Szczepienia są bezpłatne dla wszystkich mieszkańców."),
    make_doc(
        "most",
        f"Sprawdzane twierdzenie: Most w Testowie zawalił się podczas powodzi.\nOcena redakcji: Fałsz\n{BRIDGE_QUOTE}",
        source_type="factcheck",
        tier=2,
        publisher="Redakcja Testowa",
        claim_reviewed="Most w Testowie zawalił się podczas powodzi.",
        rating="Fałsz",
        appearance_urls=["https://plotki.example.com/most-runal"],
    ),
    make_doc("ludnosc-stara", "Liczba mieszkańców Testowa wynosi 120 tysięcy osób.", age_days=900),
    make_doc(
        "ludnosc-nowa",
        "Według najnowszych danych w Testowie mieszka 95 tysięcy osób.",
        source_type="factcheck",
        tier=2,
        publisher="Redakcja Testowa",
    ),
]


def claim(text: str, kind: str = "fakt", risk: str = "standard") -> ExtractedClaim:
    return ExtractedClaim(text=text, kind=kind, queries=[text], risk=risk)


def extraction(*claims: ExtractedClaim, status: str = "ok", message: str = "", injection: bool = False) -> Extraction:
    return Extraction(input_status=status, message=message, claims=list(claims), injection_detected=injection)


def assessment(verdict: Verdict, *judgements: tuple[str, str, str], justification: str = "Uzasadnienie [P1].") -> ClaimAssessment:
    return ClaimAssessment(
        judgements=[PassageJudgement(passage_id=p, stance=s, quote=q) for p, s, q in judgements],
        proposed_verdict=verdict,
        justification=justification,
        missing="",
        injection_detected=False,
    )


def passage_number(user_prompt: str, needle: str) -> str:
    """Numer fragmentu (P1, P2…), w którym model „widzi” podany tekst."""
    sources_start = user_prompt.index("Fragmenty źródeł:")
    before = user_prompt[: user_prompt.index(needle, sources_start)]
    return "P" + before.rsplit("[P", 1)[1].split("]", 1)[0]


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.fail: LLMError | None = None
        self.extract: Callable[[str], Extraction] = lambda user: extraction(claim("Twierdzenie testowe."))
        self.assess: Callable[[str], ClaimAssessment] = lambda user: assessment(Verdict.INSUFFICIENT)
        self.reading = ImageReading(text="", visible_dates=[], description="", readable=False, injection_detected=False)

    async def structured(self, *, system, user, schema, effort="medium", images=None):
        self.calls.append((schema.__name__, system, user))
        if self.fail:
            raise self.fail
        if schema is Extraction:
            return self.extract(user), Usage(100, 20, 1)
        if schema is ClaimAssessment:
            return self.assess(user), Usage(500, 80, 1)
        return self.reading, Usage(300, 50, 1)


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        admin_token="test-token",
        embeddings="off",
        rate_limit_per_minute=1000,
    )


@pytest.fixture
def make_client(settings, provider):
    def factory(**overrides) -> TestClient:
        app = create_app(with_lifespan=False)
        index = CorpusIndex(DOCS, version="test", built_at=datetime.now(UTC))
        build_state(app, settings.model_copy(update=overrides), provider=overrides.pop("provider", provider), index=index)
        return TestClient(app)

    return factory


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()
