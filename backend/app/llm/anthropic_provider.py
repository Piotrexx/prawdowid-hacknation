import base64

import anthropic
from pydantic import ValidationError

from app.llm.base import (
    ImageInput,
    LLMBadOutput,
    LLMRateLimited,
    LLMRefused,
    LLMUnavailable,
    T,
    Usage,
)

_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None, timeout_s: float):
        self.model = model
        # Bez jawnego klucza SDK samo szuka poświadczeń (zmienne środowiskowe lub profil `ant`).
        kwargs = {"api_key": api_key} if api_key else {}
        self._client = anthropic.AsyncAnthropic(timeout=timeout_s, max_retries=1, **kwargs)

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        effort: str = "medium",
        images: list[ImageInput] | None = None,
    ) -> tuple[T, Usage]:
        content: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image.media_type,
                    "data": base64.standard_b64encode(image.data).decode("ascii"),
                },
            }
            for image in images or []
        ]
        content.append({"type": "text", "text": user})
        try:
            # `create` zamiast `parse`: pomocnik SDK waliduje JSON, zanim da się sprawdzić
            # `stop_reason`, więc odmowa i ucięta odpowiedź wyglądałyby jak błąd walidacji.
            response = await self._client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_config={
                    "effort": effort,
                    "format": {"type": "json_schema", "schema": anthropic.transform_schema(schema)},
                },
                # Gdy klasyfikator bezpieczeństwa odmówi (częste przy tematach dezinformacji),
                # API samo ponawia żądanie na modelu zapasowym.
                betas=[_FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.RateLimitError as exc:
            raise LLMRateLimited(str(exc)) from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise LLMUnavailable("brak ważnego klucza API") from exc
        except anthropic.APIStatusError as exc:
            raise LLMUnavailable(f"błąd API ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMUnavailable("brak połączenia z API") from exc
        except anthropic.AnthropicError as exc:
            raise LLMUnavailable(str(exc)) from exc

        if response.stop_reason == "refusal":
            raise LLMRefused("model odmówił przetworzenia treści")
        if response.stop_reason == "max_tokens":
            raise LLMBadOutput("odpowiedź modelu została ucięta")
        text = next((block.text for block in response.content if block.type == "text"), "")
        try:
            output = schema.model_validate_json(text)
        except ValidationError as exc:
            raise LLMBadOutput("odpowiedź modelu niezgodna ze schematem") from exc
        return output, Usage(response.usage.input_tokens, response.usage.output_tokens, 1)
