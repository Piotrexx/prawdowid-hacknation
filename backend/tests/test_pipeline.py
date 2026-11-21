"""Scenariusze testowe dla pipeline'u fake news."""

from app.schemas import VerdictLabel
from tests.conftest import ADMIN

API = "/api/v1"


def _mock_verdict(verdict: VerdictLabel, confidence: float = 0.8, justification: str = "Testowe uzasadnienie."):
    """Tworzy prosty obiekt werdyktu zwracany przez fake provider."""

    class _Verdict:
        pass

    result = _Verdict()
    result.verdict = verdict
    result.confidence = confidence
    result.justification = justification
    return result


def _prepare(client, deepseek_provider, verdict: VerdictLabel, confidence: float = 0.8) -> None:
    deepseek_provider.verdict_response = _mock_verdict(verdict, confidence)


def test_fake_news_detected(client, deepseek_provider):
    _prepare(client, deepseek_provider, VerdictLabel.FAKE, 0.9)
    deepseek_provider.verdict_response.justification = "Artykuł obalony przez fact-checki."

    response = client.post(f"{API}/checks", json={"url": "https://example.org/fake-news-article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "fake_news"
    assert data["confidence"] == 0.9
    assert "fake" in data["keywords"]


def test_real_article_confirmed(client, deepseek_provider):
    _prepare(client, deepseek_provider, VerdictLabel.REAL, 0.85)

    response = client.post(f"{API}/checks", json={"url": "https://example.org/real-article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "prawdziwe"
    assert data["confidence"] == 0.85


def test_uncertain_verdict(client, deepseek_provider):
    _prepare(client, deepseek_provider, VerdictLabel.UNCERTAIN, 0.5)

    response = client.post(f"{API}/checks", json={"url": "https://example.org/uncertain-article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "niepewne"
    assert data["confidence"] == 0.5


def test_satire_detected(client, deepseek_provider):
    _prepare(client, deepseek_provider, VerdictLabel.SATIRE, 0.95)

    response = client.post(f"{API}/checks", json={"url": "https://aszdziennik.pl/satyrartykol"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "satyna"
    assert data["confidence"] == 0.95


def test_opinion_detected(client, deepseek_provider):
    _prepare(client, deepseek_provider, VerdictLabel.OPINION, 0.7)

    response = client.post(f"{API}/checks", json={"url": "https://example.org/opinion-piece"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "opinia"
    assert data["confidence"] == 0.7


def test_fetch_error_returns_technical_error(client):
    import pytest

    from app.security.urlfetch import UrlFetchError

    async def _mock_fetch_fail(url: str, settings):
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


def test_bielik_error_falls_back_to_deepseek(client, bielik_provider, deepseek_provider):
    from app.llm.base import LLMUnavailable

    _prepare(client, deepseek_provider, VerdictLabel.FAKE, 0.8)
    bielik_provider.fail = LLMUnavailable("model niedostępny")

    response = client.post(f"{API}/checks", json={"url": "https://example.org/article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["verdict"] == "fake_news"
    assert any("Bielik" in warning for warning in data["limitations"])


def test_deepseek_error_returns_technical_error(client, deepseek_provider):
    from app.llm.base import LLMUnavailable

    deepseek_provider.fail = LLMUnavailable("model niedostępny")

    response = client.post(f"{API}/checks", json={"url": "https://example.org/article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["error_code"] == "llm_unavailable"


def test_missing_provider_error(make_client):
    limited_client = make_client(provider=None)
    response = limited_client.post(f"{API}/checks", json={"url": "https://example.org/article"})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["error_code"] == "llm_not_configured"


def test_rate_limit_returns_429(make_client):
    limited = make_client(rate_limit_per_minute=1)
    limited.post(f"{API}/checks", json={"url": "https://example.org/article1"})
    response = limited.post(f"{API}/checks", json={"url": "https://example.org/article2"})

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1


def test_health_endpoint(client):
    response = client.get(f"{API}/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ("ok", "degraded")
    assert "llm_provider" in data
    assert "bielik_model" in data
    assert "google_factcheck_configured" in data
    assert "corpus_documents" in data


def test_admin_metrics_requires_token(client):
    response = client.get(f"{API}/admin/metrics")
    assert response.status_code == 401


def test_admin_metrics_with_token(client, deepseek_provider):
    _prepare(client, deepseek_provider, VerdictLabel.FAKE)
    client.post(f"{API}/checks", json={"url": "https://example.org/article1"})

    response = client.get(f"{API}/admin/metrics", headers=ADMIN)
    assert response.status_code == 200
    data = response.json()

    assert data["checks_total"] >= 1
    assert "by_verdict" in data


def test_admin_export_csv(client, deepseek_provider):
    _prepare(client, deepseek_provider, VerdictLabel.FAKE)
    client.post(f"{API}/checks", json={"url": "https://example.org/article1"})

    response = client.get(f"{API}/admin/export", params={"format": "csv"}, headers=ADMIN)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "fake_news" in response.text


def test_admin_export_json(client, deepseek_provider):
    _prepare(client, deepseek_provider, VerdictLabel.FAKE)
    client.post(f"{API}/checks", json={"url": "https://example.org/article1"})

    response = client.get(f"{API}/admin/export", params={"format": "json"}, headers=ADMIN)
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert len(data) >= 1


def test_session_deletion(client, deepseek_provider):
    _prepare(client, deepseek_provider, VerdictLabel.FAKE)

    response = client.post(
        f"{API}/checks", json={"url": "https://example.org/article", "session_id": "test-session-1"}
    )
    assert response.status_code == 200
    check_id = response.json()["id"]

    delete_response = client.delete(f"{API}/sessions/test-session-1")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] == 1

    get_response = client.get(f"{API}/checks/{check_id}")
    assert get_response.status_code == 404


def test_admin_corpus_stats(client):
    response = client.get(f"{API}/admin/corpus/stats", headers=ADMIN)
    assert response.status_code == 200
    data = response.json()
    assert "articles_total" in data
    assert "by_source" in data
    assert "runs" in data


def test_admin_ingest_rejects_unknown_source(client):
    response = client.post(
        f"{API}/admin/corpus/ingest",
        json={"sources": ["nie-ma-takiego-zrodla"]},
        headers=ADMIN,
    )
    assert response.status_code == 400


def test_invalid_url_format(client):
    response = client.post(f"{API}/checks", json={"url": "not-a-valid-url"})
    assert response.status_code == 422


def test_missing_url(client):
    response = client.post(f"{API}/checks", json={})
    assert response.status_code == 422
