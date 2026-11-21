"""Wspólne fixture'y testów. Testy wymagają PostgreSQL z pgvector.

Domyślnie korzystają z bazy `prawdowid_test` z docker-compose:
    docker compose up -d postgres
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.api.deps import CONSENT_COOKIE, SESSION_COOKIE
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
from app.retrieval.corpus import CorpusStore, SourceDocument
from app.schemas import KeywordExtraction, Verdict
from app.store.db import Store
from app.store.models import Base

ADMIN = {"X-Admin-Token": "test-token"}
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://prawdowid:prawdowid@localhost:5432/prawdowid_test",
)
TODAY = date.today()
TEST_SESSION = "sesja-testowa-0001"


def make_doc(
    doc_id: str,
    text: str,
    *,
    source_type="official",
    tier=1,
    age_days=10,
    publisher="Urząd Testowy",
    **extra,
) -> SourceDocument:
    published = TODAY - timedelta(days=age_days)
    return SourceDocument(
        external_id=doc_id,
        source_key=f"test-{source_type}",
        title=f"Dokument {doc_id}",
        publisher=publisher,
        url=f"https://example.org/{doc_id}",
        source_type=source_type,
        tier=tier,
        license="fikstura testowa",
        storage="full_text",
        published_at=published,
        text=text,
        excerpt=text,
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
        appearance_urls=("https://plotki.example.com/most-runal",),
    ),
    make_doc("ludnosc-stara", "Liczba mieszkańców Testowa wynosi 120 tysięcy osób.", age_days=900),
    make_doc(
        "ludnosc-nowa",
        "Według najnowszych danych w Testowie mieszka 95 tysięcy osób.",
        source_type="factcheck",
        tier=2,
        publisher="Redakcja Testowa",
    ),
    make_doc(
        "gazeta",
        "Jak podaje gazeta, tramwaje w Testowie od poniedziałku kursują co pięć minut.",
        source_type="media",
        tier=3,
        publisher="Gazeta Testowa",
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
        # Warstwa wspierająca: słowa kluczowe i podsumowanie całości.
        self.keywords = KeywordExtraction(
            keywords=["Testowo", "szczepienia"], main_topic="Testowy materiał", summary="Podsumowanie testowe."
        )
        self.summary: Callable[[str], object] = lambda user: _summary_model()
        # Awarie warstwy wspierającej nie mogą unieważniać ocen twierdzeń – stąd osobny przełącznik.
        self.fail_support: LLMError | None = None

    async def structured(self, *, system, user, schema, effort="medium", images=None):
        self.calls.append((schema.__name__, system, user))
        if schema.__name__ in ("KeywordExtraction", "_Summary") and self.fail_support:
            raise self.fail_support
        if self.fail:
            raise self.fail
        if schema is Extraction:
            return self.extract(user), Usage(100, 20, 1)
        if schema is ClaimAssessment:
            return self.assess(user), Usage(500, 80, 1)
        if schema is KeywordExtraction:
            return self.keywords, Usage(200, 40, 1)
        if schema.__name__ == "_Summary":
            return self.summary(user), Usage(400, 60, 1)
        return self.reading, Usage(300, 50, 1)


def _summary_model():
    from app.core.pipeline import _Summary

    return _Summary(verdict=Verdict.INSUFFICIENT, confidence=0.4, justification="Podsumowanie testowe.")


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    try:
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as exc:  # pragma: no cover - zależne od środowiska
        pytest.fail(
            "Testy wymagają PostgreSQL z pgvector. Uruchom `docker compose up -d postgres`. "
            f"Błąd: {exc}"
        )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_db(db_engine: Engine) -> Iterator[None]:
    yield
    with db_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        admin_token="test-token",
        embedding_backend="none",
        rate_limit_per_minute=1000,
        # Pusty adres wyłącza lokalny model słów kluczowych – testy nie wychodzą do sieci.
        bielik_base_url="",
        google_factcheck_api_key=None,
        archive_enabled=True,
    )


def seed_corpus(corpus: CorpusStore) -> None:
    for document in DOCS:
        corpus.upsert_document(document, content_hash=f"hash-{document.external_id}")


@pytest.fixture
def make_client(settings, provider):
    def factory(**overrides) -> TestClient:
        app = create_app(with_lifespan=False)
        store = Store(settings.database_url)
        corpus = CorpusStore(store.engine)
        seed_corpus(corpus)
        active_provider = overrides.pop("provider", provider)
        active_settings = settings.model_copy(update=overrides)
        build_state(
            app,
            active_settings,
            provider=active_provider,
            embedder=None,
            corpus=corpus,
        )
        session = TEST_SESSION
        app.state.store.record_consent(session, active_settings.privacy_policy_version, True)
        client = TestClient(app)
        client.cookies.set(SESSION_COOKIE, session)
        client.cookies.set(CONSENT_COOKIE, active_settings.privacy_policy_version)
        return client

    return factory


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def mock_fetch_page():
    """Mockuje fetch_page z urlfetch."""
    from app.security.urlfetch import FetchedPage

    async def _mock(url: str, settings: Settings) -> FetchedPage:
        return FetchedPage(
            url=url,
            title="Testowy tytuł artykułu",
            text="To jest treść testowego artykułu do weryfikacji. Zawiera pewne twierdzenia do sprawdzenia.",
            published=date.today(),
        )

    with patch("app.core.pipeline.fetch_page", _mock):
        yield


@pytest.fixture
def mock_factcheck_api():
    """Mockuje Google Fact Check API."""

    async def _mock_get(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "claims": [
                {
                    "text": "Testowe twierdzenie do sprawdzenia",
                    "claimant": "Jan Kowalski",
                    "claimDate": "2024-01-15",
                    "claimReview": [
                        {
                            "url": "https://factcheck.example.com/review/1",
                            "title": "Sprawdzenie: Testowe twierdzenie",
                            "publisher": {"name": "Demagog", "site": "demagog.org.pl"},
                            "textualRating": "Fałsz",
                        }
                    ],
                }
            ]
        }
        return mock_response

    with patch("httpx.AsyncClient.get", _mock_get):
        yield
