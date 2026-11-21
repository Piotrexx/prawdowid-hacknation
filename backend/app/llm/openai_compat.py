"""Dostawca dla API zgodnych z OpenAI Chat Completions: DeepSeek (domyślnie), Mistral (UE),
Ollama / vLLM (samodzielny hosting, np. Bielik), OpenRouter."""

import base64
import json

import httpx
from pydantic import ValidationError

from app.llm.base import (
    ImageInput,
    LLMBadOutput,
    LLMRateLimited,
    LLMUnavailable,
    T,
    Usage,
)

_ATTEMPTS = 2


class OpenAICompatProvider:
    name = "openai_compatible"

    def __init__(self, model: str, base_url: str, api_key: str | None, timeout_s: float, json_mode: str):
        self.model = model
        self._json_mode = json_mode
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout_s)

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        effort: str = "medium",
        images: list[ImageInput] | None = None,
    ) -> tuple[T, Usage]:
        json_schema = schema.model_json_schema()
        if self._json_mode == "json_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": json_schema, "strict": True},
            }
        else:
            response_format = {"type": "json_object"}
            system += "\n\nOdpowiedz wyłącznie obiektem JSON zgodnym ze schematem:\n" + json.dumps(
                json_schema, ensure_ascii=False
            )
        content: str | list[dict] = user
        if images:
            content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{i.media_type};base64,{base64.standard_b64encode(i.data).decode('ascii')}"
                    },
                }
                for i in images
            ] + [{"type": "text", "text": user}]
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "response_format": response_format,
            "temperature": 0,
        }

        usage = Usage()
        last_error: Exception | None = None
        # Jedna ponowna próba, gdy model zwróci JSON niezgodny ze schematem.
        for _ in range(_ATTEMPTS):
            try:
                response = await self._client.post("/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                raise LLMUnavailable("brak połączenia z API modelu") from exc
            if response.status_code == 429:
                raise LLMRateLimited("limit zapytań u dostawcy modelu")
            if response.status_code in (401, 403):
                raise LLMUnavailable("brak ważnego klucza API")
            if response.status_code >= 400:
                raise LLMUnavailable(f"błąd API modelu ({response.status_code})")
            body = response.json()
            reported = body.get("usage") or {}
            usage.add(Usage(reported.get("prompt_tokens", 0), reported.get("completion_tokens", 0), 1))
            try:
                return schema.model_validate_json(body["choices"][0]["message"]["content"]), usage
            except (KeyError, IndexError, TypeError, ValidationError) as exc:
                last_error = exc
        raise LLMBadOutput("odpowiedź modelu niezgodna ze schematem") from last_error
