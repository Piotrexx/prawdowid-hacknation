"""Katalog dostawców modeli dostępnych w panelu moderatora.

Ceny są orientacyjne i podane w USD za 1 mln tokenów (wejście, wyjście).
Można je nadpisać w panelu – rzeczywisty cennik zależy od umowy z dostawcą.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelOption:
    id: str
    label: str
    price_input: float | None
    price_output: float | None


@dataclass(frozen=True)
class ProviderOption:
    key: str
    name: str
    icon: str | None
    base_url: str
    requires_key: bool
    is_local: bool = False
    note: str = ""
    models: list[ModelOption] = field(default_factory=list)


PROVIDERS: tuple[ProviderOption, ...] = (
    ProviderOption(
        key="deepseek",
        name="DeepSeek",
        icon="deepseek.webp",
        base_url="https://api.deepseek.com",
        requires_key=True,
        note="Domyślny dostawca projektu. Klucz z .env jest używany, dopóki nie zapiszesz własnego.",
        models=[
            ModelOption("deepseek-flash", "DeepSeek V4.1 Flash", 0.30, 1.20),
            ModelOption("deepseek-v4-pro", "DeepSeek V4 Pro", 1.32, 3.96),
        ],
    ),
    ProviderOption(
        key="openai",
        name="OpenAI",
        icon="chatgpt.webp",
        base_url="https://api.openai.com/v1",
        requires_key=True,
        models=[
            ModelOption("gpt-5.2", "GPT-5.2", 1.75, 14.00),
            ModelOption("gpt-5.2-mini", "GPT-5.2 mini", 0.25, 2.00),
        ],
    ),
    ProviderOption(
        key="anthropic",
        name="Anthropic",
        icon="cloude.png",
        base_url="https://api.anthropic.com",
        requires_key=True,
        models=[
            ModelOption("claude-sonnet-5-5", "Claude Sonnet 5.5", 2.00, 10.00),
            ModelOption("claude-haiku-5-5", "Claude Haiku 5.5", 0.10, 0.50),
            ModelOption("claude-opus-5-5", "Claude Opus 5.5", 4.00, 20.00),
        ],
    ),
    ProviderOption(
        key="gemini",
        name="Google Gemini",
        icon="gemini.webp",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        requires_key=True,
        note="Gemini przez warstwę zgodną z OpenAI.",
        models=[
            ModelOption("gemini-3-pro", "Gemini 3 Pro", 1.25, 10.00),
            ModelOption("gemini-3-flash", "Gemini 3 Flash", 0.30, 2.50),
        ],
    ),
    ProviderOption(
        key="openrouter",
        name="OpenRouter",
        icon="openrouter.svg",
        base_url="https://openrouter.ai/api/v1",
        requires_key=True,
        note="Jedno API do wielu modeli. Ceny ustala model wybrany u dostawcy.",
        models=[
            ModelOption("anthropic/claude-sonnet-5-5", "Claude Sonnet 5.5", 2.00, 10.00),
            ModelOption("openai/gpt-5.2", "GPT-5.2", 1.75, 14.00),
            ModelOption("openrouter/auto", "OpenRouter Auto", None, None),
        ],
    ),
    ProviderOption(
        key="local",
        name="Model lokalny",
        icon=None,
        base_url="http://localhost:11434/v1",
        requires_key=False,
        is_local=True,
        note="Ollama albo vLLM na tym samym serwerze. Wpisz dokładną nazwę modelu; koszt przyjmujemy jako 0.",
        models=[
            ModelOption("local-model", "Własny model lokalny", 0.0, 0.0),
        ],
    ),
)

PROVIDERS_BY_KEY: dict[str, ProviderOption] = {provider.key: provider for provider in PROVIDERS}
DEFAULT_PROVIDER = "deepseek"


def provider_catalog() -> list[ProviderOption]:
    return list(PROVIDERS)


def default_model(provider_key: str) -> ModelOption | None:
    provider = PROVIDERS_BY_KEY.get(provider_key)
    return provider.models[0] if provider and provider.models else None
