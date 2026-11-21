"""Scenariusze testowe dla nowego pipeline'u fake news."""

import pytest
from unittest.mock import MagicMock

from app.schemas import VerdictLabel, CheckStatus
from tests.conftest import ADMIN

API = "/api/v1"


def _mock_verdict(verdict: VerdictLabel, confidence: float = 0.8, justification: str = "Testowe uzasadnienie."):
    """Tworzy mock obiektu werdyktu."""
    return type('obj', (object,), {
        'verdict': verdict,
        'confidence': confidence,
        'justification': justification
    })()


async def test_fake_news_detected(client):
    """Test wykrycia fake news."""
    from tests.conftest import deepseek_provider, bielik_provider
    deepseek_provider.verdict_response = _mock_verdict(VerdictLabel.FAKE, 0.9, "Artykuł zawiera fałszywe informacje obalone przez fact-checki.")

    response = client.post(f"{API}/checks", json={"url": "https://example.org/fake-news-article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "fake_news"
    assert data["confidence"] == 0.9
    assert "fake" in data["keywords"]


async def test_real_article_confirmed(client):
    """Test potwierdzenia prawdziwego artykułu."""
    from tests.conftest import deepseek_provider, bielik_provider
    deepseek_provider.verdict_response = _mock_verdict(VerdictLabel.REAL, 0.85, "Główne twierdzenia są wspierane przez wiarygodne źródła.")

    response = client.post(f"{API}/checks", json={"url": "https://example.org/real-article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "prawdziwe"
    assert data["confidence"] == 0.85


async def test_uncertain_verdict(client):
    """Test werdyktu niepewnego."""
    from tests.conftest import deepseek_provider, bielik_provider
    deepseek_provider.verdict_response = _mock_verdict(VerdictLabel.UNCERTAIN, 0.5, "Brak wystarczających dowodów.")

    response = client.post(f"{API}/checks", json={"url": "https://example.org/uncertain-article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "niepewne"
    assert data["confidence"] == 0.5


async def test_satire_detected(client):
    """Test wykrycia satyry."""
    from tests.conftest import deepseek_provider, bielik_provider
    deepseek_provider.verdict_response = _mock_verdict(VerdictLabel.SATIRE, 0.95, "Artykuł pochodzi ze znanej strony satyrycznej.")

    response = client.post(f"{API}/checks", json={"url": "https://aszdziennik.pl/satyrartykol"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "satyna"
    assert data["confidence"] == 0.95


async def test_opinion_detected(client):
    """Test wykrycia opinii."""
    from tests.conftest import deepseek_provider, bielik_provider
    deepseek_provider.verdict_response = _mock_verdict(VerdictLabel.OPINION, 0.7, "Artykuł wyraża opinię autora, nie stwierdza faktów.")

    response = client.post(f"{API}/checks", json={"url": "https://example.org/opinion-piece"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "opinia"
    assert data["confidence"] == 0.7


async def test_fetch_error_returns_technical_error(client):
    """Test błędu pobierania zwraca błąd techniczny, nie werdykt."""
    from tests.conftest import mock_fetch_page

    async def _mock_fetch_fail(url: str, settings):
        from app.security.urlfetch import UrlFetchError
        raise UrlFetchError("url_unreachable", "Nie udało się połączyć z tą stroną.")

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("app.core.pipeline.fetch_page", _mock_fetch_fail)
        response = client.post(f"{API}/checks", json={"url": "https://unreachable.example.org/article"})
        assert response.status_code == 200
        data = response.json()

    assert data["status"] == "error"
    assert data["error_code"] == "url_unreachable"
    assert "nie wynik sprawdzenia" in data["status_message"]
    assert data["verdict"] is None


async def test_bielik_error_returns_technical_error(client, bielik_provider):
    """Test błędu modelu Bielik zwraca błąd techniczny."""
    from app.llm.base import LLMUnavailable
    bielik_provider.fail = LLMUnavailable("model niedostępny")

    response = client.post(f"{API}/checks", json={"url": "https://example.org/article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["error_code"] == "llm_unavailable"
    assert "nie wynik sprawdzenia" in data["status_message"]


async def test_deepseek_error_returns_technical_error(client, deepseek_provider):
    """Test błędu modelu DeepSeek zwraca błąd techniczny."""
    from app.llm.base import LLMUnavailable
    deepseek_provider.fail = LLMUnavailable("model niedostępny")

    response = client.post(f"{API}/checks", json={"url": "https://example.org/article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["error_code"] == "llm_unavailable"


async def test_missing_provider_error(client):
    """Test braku skonfigurowanego providera LLM."""
    from tests.conftest import make_client
    limited_client = make_client(provider=None)
    response = limited_client.post(f"{API}/checks", json={"url": "https://example.org/article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["error_code"] == "llm_not_configured"


async def test_rate_limit_returns_429(client):
    """Test limitu zapytań."""
    from tests.conftest import make_client
    limited = make_client(rate_limit_per_minute=1)
    limited.post(f"{API}/checks", json={"url": "https://example.org/article1"})
    response = limited.post(f"{API}/checks", json={"url": "https://example.org/article2"})

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1


async def test_health_endpoint(client):
    """Test endpointu health."""
    response = client.get(f"{API}/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ("ok", "degraded")
    assert "llm_provider" in data
    assert "bielik_model" in data
    assert "google_factcheck_configured" in data


async def test_admin_metrics_requires_token(client):
    """Test że metryki wymagają tokena."""
    response = client.get(f"{API}/admin/metrics")
    assert response.status_code == 401


async def test_admin_metrics_with_token(client):
    """Test metryk z tokenem."""
    from tests.conftest import deepseek_provider, bielik_provider
    deepseek_provider.verdict_response = _mock_verdict(VerdictLabel.FAKE)

    client.post(f"{API}/checks", json={"url": "https://example.org/article1"})

    response = client.get(f"{API}/admin/metrics", headers=ADMIN)
    assert response.status_code == 200
    data = response.json()

    assert data["checks_total"] >= 1
    assert "by_verdict" in data


async def test_admin_export_csv(client):
    """Test eksportu CSV."""
    from tests.conftest import deepseek_provider, bielik_provider
    deepseek_provider.verdict_response = _mock_verdict(VerdictLabel.FAKE)

    client.post(f"{API}/checks", json={"url": "https://example.org/article1"})

    response = client.get(f"{API}/admin/export", params={"format": "csv"}, headers=ADMIN)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "fake_news" in response.text


async def test_admin_export_json(client):
    """Test eksportu JSON."""
    from tests.conftest import deepseek_provider, bielik_provider
    deepseek_provider.verdict_response = _mock_verdict(VerdictLabel.FAKE)

    client.post(f"{API}/checks", json={"url": "https://example.org/article1"})

    response = client.get(f"{API}/admin/export", params={"format": "json"}, headers=ADMIN)
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert len(data) >= 1


async def test_session_deletion(client):
    """Test usuwania sesji."""
    from tests.conftest import deepseek_provider, bielik_provider
    deepseek_provider.verdict_response = _mock_verdict(VerdictLabel.FAKE)

    response = client.post(f"{API}/checks", json={"url": "https://example.org/article", "session_id": "test-session-1"})
    assert response.status_code == 200
    check_id = response.json()["id"]

    delete_response = client.delete(f"{API}/sessions/test-session-1")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] == 1

    get_response = client.get(f"{API}/checks/{check_id}")
    assert get_response.status_code == 404


async def test_invalid_url_format(client):
    """Test niepoprawnego formatu URL."""
    response = client.post(f"{API}/checks", json={"url": "not-a-valid-url"})
    assert response.status_code == 422  # Pydantic validation error


async def test_missing_url(client):
    """Test braku URL w żądaniu."""
    response = client.post(f"{API}/checks", json={})
    assert response.status_code == 422  # Pydantic validation error