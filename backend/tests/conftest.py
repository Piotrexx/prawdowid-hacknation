"""Testy dla nowego pipeline'u fake news: URL -> trafilatura -> Bielik -> Google Fact Check -> DeepSeek."""

from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.pipeline import VerificationService
from app.llm.base import LLMError, LLMProvider, Usage
from app.main import build_state, create_app
from app.schemas import CheckResponse, CheckStatus, VerdictLabel, FactCheckResult, KeywordExtraction
from app.store.db import Store

ADMIN = {"X-Admin-Token": "test-token"}


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
        if schema.__name__ == "VerdictOnly":
            return self.verdict_response, Usage(500, 100, 1)
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
            summary="Artykuł testowy do weryfikacji."
        )

    async def structured(self, *, system: str, user: str, schema, effort: str = "medium", images=None):
        self.calls.append((schema.__name__, system, user))
        if self.fail:
            raise self.fail
        return self.keywords_response, Usage(200, 50, 1)


@pytest.fixture
def deepseek_provider() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
def bielik_provider() -> FakeBielikProvider:
    return FakeBielikProvider()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        admin_token="test-token",
        rate_limit_per_minute=1000,
        llm_provider="openai_compatible",
        llm_model="deepseek-flash",
        llm_base_url="https://api.deepseek.com",
        bielik_base_url="http://localhost:11434",
        bielik_model="bielik:4.5b-instruct",
        google_factcheck_api_key=None,
    )


@pytest.fixture
def mock_fetch_page():
    """Mockuje fetch_page z urlfetch."""
    from app.security.urlfetch import FetchedPage
    from datetime import date
    from unittest.mock import patch

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
    from unittest.mock import patch
    import httpx

    async def _mock_get(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "claims": [
                {
                    "text": "Testowe twierdzenie do sprawdzenia",
                    "claimant": "Jan Kowalski",
                    "claimDate": "2024-01-15",
                    "claimReview": [{
                        "url": "https://factcheck.example.com/review/1",
                        "title": "Sprawdzenie: Testowe twierdzenie",
                        "publisher": {"name": "Demagog", "site": "demagog.org.pl"},
                        "textualRating": "Fałsz",
                    }],
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

        # Build service with fake providers
        store = Store(settings.database_url)

        # Monkey-patch the service providers
        service = VerificationService(
            settings=settings,
            provider=overrides.get("provider", deepseek_provider),
            store=store,
        )
        service._bielik_provider = overrides.get("bielik_provider", bielik_provider)

        app.state.settings = settings
        app.state.store = store
        app.state.service = service
        app.state.limiter = None  # No rate limiting in tests

        return TestClient(app)

    return factory


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()