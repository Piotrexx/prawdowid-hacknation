"""Lokalny model na CPU to najwolniejszy etap: wołamy go raz, w tle, i nie czekamy na niego dłużej niż trzeba."""

import asyncio
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import CONSENT_COOKIE, SESSION_COOKIE
from app.llm.base import LLMUnavailable, Usage
from app.llm.openai_compat import OpenAICompatProvider
from app.main import build_state, create_app
from app.retrieval.corpus import CorpusStore
from app.schemas import KeywordExtraction
from app.store.db import Store
from tests.conftest import TEST_SESSION, extraction, seed_corpus

API = "/api/v1"
CLAIM_TEXT = "Most w Testowie zawalił się podczas powodzi."


class CountingBielik:
    name = "fake-bielik"
    model = "bielik-test"

    def __init__(self, keywords: list[str] | None = None):
        self.calls = 0
        self.keywords = keywords or []

    async def structured(self, *, system, user, schema, effort="medium", images=None):
        assert schema is KeywordExtraction
        self.calls += 1
        return KeywordExtraction(keywords=self.keywords, main_topic="Most w Testowie"), Usage(100, 20, 1)


class SlowBielik(CountingBielik):
    async def structured(self, *, system, user, schema, effort="medium", images=None):
        self.calls += 1
        await asyncio.sleep(5)
        raise AssertionError("powinno zostać przerwane")


class BrokenBielik(CountingBielik):
    async def structured(self, *, system, user, schema, effort="medium", images=None):
        self.calls += 1
        raise LLMUnavailable("brak połączenia")


@pytest.fixture
def make_bielik_client(settings, provider):
    def factory(bielik: CountingBielik) -> TestClient:
        app = create_app(with_lifespan=False)
        corpus = CorpusStore(Store(settings.database_url).engine)
        seed_corpus(corpus)
        build_state(app, settings, provider=provider, bielik_provider=bielik, embedder=None, corpus=corpus)
        app.state.store.record_consent(TEST_SESSION, settings.privacy_policy_version, True)
        client = TestClient(app)
        client.cookies.set(SESSION_COOKIE, TEST_SESSION)
        client.cookies.set(CONSENT_COOKIE, settings.privacy_policy_version)
        return client

    return factory


def check(client, text: str = CLAIM_TEXT) -> dict:
    response = client.post(f"{API}/checks", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_bielik_keywords_are_used_from_a_single_call(make_bielik_client, provider):
    bielik = CountingBielik(["Most w Testowie", "powódź"])

    data = check(make_bielik_client(bielik))

    assert data["status"] == "completed"
    assert bielik.calls == 1
    assert (data["keywords"], data["main_topic"]) == (["Most w Testowie", "powódź"], "Most w Testowie")
    assert "bielik" in data["meta"]["stages_ms"]
    assert not any(name == "KeywordExtraction" for name, _, _ in provider.calls)


@pytest.mark.parametrize(
    "bielik", [CountingBielik([]), SlowBielik(), BrokenBielik()], ids=["no-keywords", "timeout", "error"]
)
def test_bielik_never_blocks_or_rejects_the_check(make_bielik_client, provider, settings, bielik):
    settings.bielik_keywords_timeout_s = 0.2

    data = check(make_bielik_client(bielik))

    assert data["status"] == "completed"
    assert bielik.calls == 1
    # Bez dodatkowego wywołania modelu: słowa kluczowe to zapytania z etapu wydzielania twierdzeń.
    assert data["keywords"] == ["Twierdzenie testowe."]
    assert not any(name == "KeywordExtraction" for name, _, _ in provider.calls)
    assert any(w["code"] == "keywords_degraded" for w in data["warnings"])


def test_out_of_scope_does_not_wait_for_a_slow_bielik(make_bielik_client, provider, settings):
    settings.bielik_keywords_timeout_s = 10
    provider.extract = lambda user: extraction(status="out_of_scope", message="To nie jest informacja do sprawdzenia.")
    client = make_bielik_client(SlowBielik())

    started = time.perf_counter()
    data = check(client, "Napisz mi wiersz o jesieni, proszę bardzo.")

    assert data["status"] == "out_of_scope"
    assert time.perf_counter() - started < 2


def test_local_model_requests_are_capped():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        body = {"choices": [{"message": {"content": '{"keywords": ["a"], "main_topic": "b"}'}}], "usage": {}}
        return httpx.Response(200, json=body)

    bielik = OpenAICompatProvider(
        model="bielik", base_url="http://ollama", api_key=None, timeout_s=5, json_mode="json_object", max_tokens=256
    )
    bielik._client = httpx.AsyncClient(base_url="http://ollama", transport=httpx.MockTransport(handler))

    asyncio.run(bielik.structured(system="s", user="u", schema=KeywordExtraction))

    assert seen["max_tokens"] == 256
