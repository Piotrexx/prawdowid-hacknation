"""Testy jednostkowe dla nowego pipeline'u fake news."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.config import Settings
from app.core.pipeline import VerificationService, _Stop, CheckStatus
from app.llm.base import LLMError, Usage
from app.schemas import CheckRequest, CheckResponse, VerdictLabel, KeywordExtraction, FactCheckResult
from app.security.ratelimit import RateLimiter
from app.security.urlfetch import UrlFetchError, fetch_page


def test_rate_limiter_blocks_after_limit():
    limiter = RateLimiter(limit=2)
    assert limiter.retry_after("a") is None and limiter.retry_after("a") is None
    assert limiter.retry_after("a") >= 1
    assert limiter.retry_after("b") is None


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("http://127.0.0.1/admin", "url_not_allowed"),
        ("http://localhost/", "url_not_allowed"),
        ("http://[::1]/", "url_not_allowed"),
        ("http://169.254.169.254/latest/meta-data/", "url_not_allowed"),
        ("http://example.org:8080/", "url_not_allowed"),
        ("http://user:pass@example.org/", "url_not_allowed"),
        ("ftp://example.org/plik", "url_invalid"),
        ("file:///etc/passwd", "url_invalid"),
    ],
)
def test_url_fetch_refuses_non_public_targets(url, code):
    with pytest.raises(UrlFetchError) as error:
        asyncio.run(fetch_page(url, Settings(_env_file=None)))
    assert error.value.code == code


class MockProvider:
    """Mock LLM provider for testing."""
    name = "openai_compatible"
    model = "deepseek-flash"

    def __init__(self):
        self.fail: LLMError | None = None
        self.verdict_response = None

    async def structured(self, *, system: str, user: str, schema, effort: str = "medium", images=None):
        if self.fail:
            raise self.fail
        if schema.__name__ == "_VerdictOnly":
            return self.verdict_response, Usage(500, 100, 1)
        return MagicMock(), Usage(100, 20, 1)


class MockBielikProvider:
    """Mock Bielik provider for testing."""
    name = "openai_compatible"
    model = "bielik:4.5b-instruct"

    def __init__(self):
        self.fail: LLMError | None = None
        self.keywords_response = KeywordExtraction(
            keywords=["test", "fake", "news", "weryfikacja"],
            main_topic="Testowy artykuł o fake news",
            summary="Artykuł testowy do weryfikacji."
        )

    async def structured(self, *, system: str, user: str, schema, effort: str = "medium", images=None):
        if self.fail:
            raise self.fail
        return self.keywords_response, Usage(200, 50, 1)


from app.store.db import Store
from app.main import build_state, create_app


def _create_test_service(settings, deepseek_provider, bielik_provider):
    """Tworzy serwis weryfikacji z mockowanymi providerami."""
    store = Store(settings.database_url)
    service = VerificationService(
        settings=settings,
        provider=deepseek_provider,
        store=store,
    )
    service._bielik_provider = bielik_provider
    return service


@pytest.fixture
def test_settings(tmp_path):
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
def deepseek_provider():
    return MockProvider()


@pytest.fixture
def bielik_provider():
    return MockBielikProvider()


@pytest.fixture
def mock_fetch():
    from app.security.urlfetch import FetchedPage
    from datetime import date

    async def _mock(url: str, settings: Settings) -> FetchedPage:
        return FetchedPage(
            url=url,
            title="Testowy tytuł: Fake News Detection",
            text="To jest treść testowego artykułu do weryfikacji. Zawiera pewne twierdzenia do sprawdzenia. "
                 "Według ekspertów fake news to poważny problem.",
            published=date.today(),
        )

    with patch("app.core.pipeline.fetch_page", _mock):
        yield


@pytest.fixture
def mock_factcheck_empty():
    import httpx
    from unittest.mock import MagicMock

    async def _mock_get(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"claims": []}
        return mock_response

    with patch("httpx.AsyncClient.get", _mock_get):
        yield


async def test_full_pipeline_success(test_settings, deepseek_provider, bielik_provider, mock_fetch, mock_factcheck_empty):
    """Test pełnego pipeline'u: fetch -> keywords -> factcheck -> verdict."""
    deepseek_provider.verdict_response = type('obj', (object,), {
        'verdict': VerdictLabel.FAKE,
        'confidence': 0.85,
        'justification': "Artykuł zawiera fałszywe informacje."
    })()

    service = _create_test_service(test_settings, deepseek_provider, bielik_provider)

    request = CheckRequest(url="https://example.org/test-article")
    response = await service.check(request)

    assert response.status == CheckStatus.COMPLETED
    assert response.verdict == VerdictLabel.FAKE
    assert response.confidence == 0.85
    assert "fake" in response.keywords
    assert response.fact_check_results == []


async def test_pipeline_fetch_error(test_settings, deepseek_provider, bielik_provider):
    """Test obsługi błędu pobierania artykułu."""
    from unittest.mock import patch

    async def _mock_fetch_fail(url: str, settings: Settings):
        raise UrlFetchError("url_unreachable", "Nie udało się połączyć z tą stroną.")

    with patch("app.core.pipeline.fetch_page", _mock_fetch_fail):
        service = _create_test_service(test_settings, deepseek_provider, bielik_provider)
        request = CheckRequest(url="https://example.org/test-article")
        response = await service.check(request)

    assert response.status == CheckStatus.ERROR
    assert response.error_code == "url_unreachable"


async def test_pipeline_bielik_error(test_settings, deepseek_provider, bielik_provider, mock_fetch):
    """Test obsługi błędu modelu Bielik."""
    from app.llm.base import LLMUnavailable

    bielik_provider.fail = LLMUnavailable("model niedostępny")

    service = _create_test_service(test_settings, deepseek_provider, bielik_provider)
    request = CheckRequest(url="https://example.org/test-article")
    response = await service.check(request)

    assert response.status == CheckStatus.ERROR
    assert response.error_code == "llm_unavailable"


async def test_pipeline_deepseek_error(test_settings, deepseek_provider, bielik_provider, mock_fetch):
    """Test obsługi błędu modelu DeepSeek."""
    from app.llm.base import LLMUnavailable

    deepseek_provider.fail = LLMUnavailable("model niedostępny")

    service = _create_test_service(test_settings, deepseek_provider, bielik_provider)
    request = CheckRequest(url="https://example.org/test-article")
    response = await service.check(request)

    assert response.status == CheckStatus.ERROR
    assert response.error_code == "llm_unavailable"


async def test_pipeline_no_google_factcheck_key(test_settings, deepseek_provider, bielik_provider, mock_fetch):
    """Test pipeline'u bez klucza Google Fact Check (powinien działać, z ostrzeżeniem)."""
    deepseek_provider.verdict_response = type('obj', (object,), {
        'verdict': VerdictLabel.UNCERTAIN,
        'confidence': 0.5,
        'justification': "Brak danych do weryfikacji."
    })()

    # Upewniamy się, że nie ma klucza
    test_settings.google_factcheck_api_key = None

    service = _create_test_service(test_settings, deepseek_provider, bielik_provider)
    request = CheckRequest(url="https://example.org/test-article")
    response = await service.check(request)

    assert response.status == CheckStatus.COMPLETED
    assert response.verdict == VerdictLabel.UNCERTAIN
    assert any("Google Fact Check API nie jest skonfigurowane" in w for w in response.limitations)


# Import dla MagicMock
from unittest.mock import MagicMock