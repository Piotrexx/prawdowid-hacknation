"""Kształt żądań do dostawców modelu, sprawdzany na atrapie transportu HTTP (bez sieci i bez klucza)."""

import asyncio
import json

import anthropic
import httpx
import httpx2
import pytest

from app.config import Settings
from app.core.prompts import ClaimAssessment, Extraction
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import ImageInput, LLMBadOutput, LLMRateLimited, LLMRefused, LLMUnavailable
from app.llm.factory import build_provider
from app.llm.openai_compat import OpenAICompatProvider

EXTRACTION = {
    "input_status": "ok",
    "message": "",
    "claims": [{"text": "Twierdzenie.", "kind": "fakt", "queries": ["a", "b"], "risk": "standard"}],
    "injection_detected": False,
}


def anthropic_provider(handler) -> AnthropicProvider:
    provider = AnthropicProvider("claude-opus-5-5", "test-key", 5.0)
    provider._client = anthropic.AsyncAnthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return provider


def anthropic_reply(text: str, stop_reason: str = "end_turn") -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 120, "output_tokens": 30},
    }


def test_anthropic_request_uses_structured_output_and_keeps_instructions_in_system():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["headers"], seen["body"] = request.headers, json.loads(request.content)
        return httpx2.Response(200, json=anthropic_reply(json.dumps(EXTRACTION)))

    output, usage = asyncio.run(
        anthropic_provider(handler).structured(
            system="ZASADY", user="DANE", schema=Extraction, effort="low", images=[ImageInput(b"\x89PNG", "image/png")]
        )
    )

    body = seen["body"]
    assert output.claims[0].text == "Twierdzenie." and (usage.input_tokens, usage.output_tokens) == (120, 30)
    assert body["model"] == "claude-opus-5-5" and body["system"] == "ZASADY"
    assert [block["type"] for block in body["messages"][0]["content"]] == ["image", "text"]
    assert body["messages"][0]["content"][1]["text"] == "DANE"
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "claims" in body["output_config"]["format"]["schema"]["properties"]
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["headers"]["anthropic-beta"]
    # Model nie dostaje narzędzi ani parametrów próbkowania odrzucanych przez bieżące modele.
    assert not {"tools", "temperature", "thinking"} & body.keys()


@pytest.mark.parametrize(
    ("status", "payload", "error"),
    [
        (200, anthropic_reply("", "refusal"), LLMRefused),
        (200, anthropic_reply('{"input_status": "ok"', "max_tokens"), LLMBadOutput),
        (429, {"type": "error", "error": {"type": "rate_limit_error", "message": "x"}}, LLMRateLimited),
        (401, {"type": "error", "error": {"type": "authentication_error", "message": "x"}}, LLMUnavailable),
        (529, {"type": "error", "error": {"type": "overloaded_error", "message": "x"}}, LLMUnavailable),
    ],
)
def test_anthropic_failures_become_typed_technical_errors(status, payload, error):
    provider = anthropic_provider(lambda request: httpx2.Response(status, json=payload))
    with pytest.raises(error):
        asyncio.run(provider.structured(system="s", user="u", schema=Extraction))


def openai_provider(handler, json_mode: str = "json_schema") -> OpenAICompatProvider:
    provider = OpenAICompatProvider("mistral-large-latest", "https://llm.example/v1", "klucz", 5.0, json_mode)
    provider._client = httpx.AsyncClient(base_url="https://llm.example/v1", transport=httpx.MockTransport(handler))
    return provider


def openai_reply(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 50, "completion_tokens": 10}}


def test_openai_compatible_request_and_retry_on_invalid_json():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=openai_reply("to nie JSON" if len(bodies) == 1 else json.dumps(EXTRACTION)))

    output, usage = asyncio.run(openai_provider(handler).structured(system="ZASADY", user="DANE", schema=Extraction))

    assert output.input_status == "ok" and usage.calls == 2 and usage.input_tokens == 100
    assert bodies[0]["messages"] == [{"role": "system", "content": "ZASADY"}, {"role": "user", "content": "DANE"}]
    assert bodies[0]["response_format"]["json_schema"]["name"] == "Extraction"


def test_openai_compatible_json_object_mode_and_errors():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=openai_reply("{}"))

    with pytest.raises(LLMBadOutput):
        asyncio.run(openai_provider(handler, "json_object").structured(system="s", user="u", schema=ClaimAssessment))
    assert seen[0]["response_format"] == {"type": "json_object"} and "proposed_verdict" in seen[0]["messages"][0]["content"]

    with pytest.raises(LLMRateLimited):
        asyncio.run(openai_provider(lambda r: httpx.Response(429)).structured(system="s", user="u", schema=Extraction))
    with pytest.raises(LLMUnavailable):
        asyncio.run(openai_provider(lambda r: httpx.Response(503)).structured(system="s", user="u", schema=Extraction))


def test_default_model_is_deepseek_flash_and_needs_a_key():
    assert build_provider(Settings(_env_file=None)) is None
    provider = build_provider(Settings(_env_file=None, llm_api_key="klucz"))

    assert isinstance(provider, OpenAICompatProvider) and provider.model == "deepseek-flash"
    assert str(provider._client.base_url).rstrip("/") == "https://api.deepseek.com"
    assert provider._json_mode == "json_object"
    # Serwer lokalny (http://) działa bez klucza.
    assert build_provider(Settings(_env_file=None, llm_base_url="http://localhost:11434/v1")) is not None
