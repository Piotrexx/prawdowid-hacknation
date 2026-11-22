import os
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import Settings
from app.llm.base import LLMProvider

if TYPE_CHECKING:
    from app.llm.runtime import LlmConfig


def llm_configured(settings: Settings) -> bool:
    if settings.llm_provider == "anthropic":
        # SDK przyjmuje klucz z konfiguracji, ze środowiska albo z profilu `ant auth login`.
        return bool(
            settings.anthropic_api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or (Path.home() / ".config" / "anthropic").is_dir()
        )
    if settings.llm_provider == "openai_compatible":
        # Serwer lokalny (Ollama, vLLM pod adresem http://) zwykle nie wymaga klucza; usługi w chmurze tak.
        return bool(settings.llm_api_key) or settings.llm_base_url.startswith("http://")
    return False


def build_provider(settings: Settings) -> LLMProvider | None:
    """Zwraca None, gdy model nie jest skonfigurowany – usługa zgłasza wtedy jawny błąd techniczny."""
    if not llm_configured(settings):
        return None
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        return AnthropicProvider(settings.llm_model, key, settings.llm_timeout_s)
    from app.llm.openai_compat import OpenAICompatProvider

    key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    return OpenAICompatProvider(
        settings.llm_model, settings.llm_base_url, key, settings.llm_timeout_s, settings.llm_json_mode
    )


def build_runtime_provider(
    settings: Settings,
    config: "LlmConfig",
    api_key: str | None,
) -> LLMProvider | None:
    """Buduje dostawcę dla wyboru z panelu. Brak wymaganego klucza = None (usługa jawnie zgłasza brak modelu)."""
    if config.spec.requires_key and not api_key:
        return None
    if config.provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        base_url = config.base_url if config.base_url != config.spec.base_url else None
        return AnthropicProvider(config.model, api_key, settings.llm_timeout_s, base_url)
    from app.llm.openai_compat import OpenAICompatProvider

    return OpenAICompatProvider(
        config.model,
        config.base_url or config.spec.base_url,
        api_key,
        settings.llm_timeout_s,
        config.json_mode,
        name=config.provider,
    )
