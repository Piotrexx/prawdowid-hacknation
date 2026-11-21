"""Wspólne fixture'y testów. Testy wymagają PostgreSQL z pgvector.

Domyślnie korzystają z bazy `prawdowid_test` z docker-compose:
    docker compose up -d postgres
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import Settings
from app.core.pipeline import VerificationService
from app.llm.base import LLMError, Usage
from app.main import create_app
from app.retrieval.corpus import CorpusStore
from app.schemas import KeywordExtraction
from app.store.db import Store
from app.store.models import Base

ADMIN = {"X-Admin-Token": "test-token"}
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://prawdowid:prawdowid@localhost:5432/prawdowid_test",
)


class FakeLLMProvider:
    """Fake provider dla DeepSeek (werdykt)."""

    name = "openai_compatible"
    model = "deepseek-flash"

    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []
        self.fail: LLMError | None = None
        self.verdict_response = None

    async def structured(self, *, system: str, user: str, schema, effort: str = "medium", images=None):
        self.calls.append((schema.__name__, system, user))
        if self.fail:
            raise self.fail
        if schema.__name__ in ("VerdictOnly", "_VerdictOnly"):
            return self.verdict_response, Usage(500, 100, 1)
        if schema.__name__ == "KeywordExtraction":
            return (
                KeywordExtraction(
                    keywords=["test", "fake", "news", "weryfikacja"],
                    main_topic="Testowy artykuł o fake news",
                    summary="Artykuł testowy do weryfikacji.",
                ),
                Usage(100, 20, 1),
            )
        return MagicMock(), Usage(100, 20, 1)


class FakeBielikProvider:
    """Fake provider dla Bielik (słowa kluczowe)."""

    name = "openai_compatible"
    model = "bielik:4.5b-instruct"

    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []
        self.fail: LLMError | None = None
        self.keywords_response = KeywordExtraction(
            keywords=["test", "fake", "news", "weryfikacja"],
            main_topic="Testowy artykuł o fake news",
            summary="Artykuł testowy do weryfikacji.",
        )

    async def structured(self, *, system: str, user: str, schema, effort: str = "medium", images=None):
        self.calls.append((schema.__name__, system, user))
        if self.fail:
            raise self.fail
        return self.keywords_response, Usage(200, 50, 1)


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
def deepseek_provider() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
def bielik_provider() -> FakeBielikProvider:
    return FakeBielikProvider()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        admin_token="test-token",
        rate_limit_per_minute=1000,
        llm_provider="openai_compatible",
        llm_model="deepseek-flash",
        llm_base_url="https://api.deepseek.com",
        bielik_base_url="http://localhost:11434",
        bielik_model="bielik:4.5b-instruct",
        google_factcheck_api_key=None,
        embedding_backend="none",
    )


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


@pytest.fixture
def make_client(settings, deepseek_provider, bielik_provider, mock_fetch_page):
    def factory(**overrides) -> TestClient:
        app = create_app(with_lifespan=False)
        store = Store(settings.database_url)
        service = VerificationService(
            settings=settings,
            provider=overrides.get("provider", deepseek_provider),
            store=store,
            retriever=overrides.get("retriever"),
        )
        service._bielik_provider = overrides.get("bielik_provider", bielik_provider)

        app.state.settings = settings
        app.state.store = store
        app.state.corpus = overrides.get("corpus", CorpusStore(store.engine))
        app.state.embedder = None
        app.state.ingest_running = False
        app.state.service = service
        from app.security.ratelimit import RateLimiter

        app.state.limiter = RateLimiter(
            overrides.get("rate_limit_per_minute", settings.rate_limit_per_minute)
        )

        return TestClient(app)

    return factory


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()
