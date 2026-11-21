"""Warstwa abstrakcji nad modelem językowym. Logika weryfikacji zna tylko `LLMProvider`."""

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# USD za 1 mln tokenów (wejście, wyjście) – cenniki dostawców, stan na 2026-11.
# DeepSeek: stawki godzin szczytu (poza szczytem połowa), więc szacunek jest górną granicą.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "deepseek-flash": (0.30, 1.20),
    "deepseek-v4-pro": (1.32, 3.96),
    "claude-fable-5-2": (8.00, 40.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.calls += other.calls


@dataclass(frozen=True)
class ImageInput:
    data: bytes
    media_type: str


class LLMError(Exception):
    """Problem techniczny po stronie modelu – nigdy nie jest werdyktem."""

    code = "llm_error"


class LLMUnavailable(LLMError):
    code = "llm_unavailable"


class LLMRateLimited(LLMError):
    code = "llm_rate_limited"


class LLMRefused(LLMError):
    code = "llm_refused"


class LLMBadOutput(LLMError):
    code = "llm_bad_output"


class LLMProvider(Protocol):
    name: str
    model: str

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        effort: str = "medium",
        images: list[ImageInput] | None = None,
    ) -> tuple[T, Usage]:
        """Zwraca odpowiedź zwalidowaną względem `schema`. Model nie dostaje żadnych narzędzi."""
        ...


def estimate_cost(model: str, usage: Usage, override: tuple[float | None, float | None] = (None, None)) -> float | None:
    price_in, price_out = override
    if price_in is None or price_out is None:
        if model not in PRICES_PER_MTOK:
            return None
        price_in, price_out = PRICES_PER_MTOK[model]
    return round((usage.input_tokens * price_in + usage.output_tokens * price_out) / 1_000_000, 6)
