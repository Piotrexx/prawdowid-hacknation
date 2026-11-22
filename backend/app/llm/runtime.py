"""Konfiguracja modelu językowego zmieniana z panelu.

Wybór z panelu jest zapisywany w tabeli `app_settings` i nadpisuje wartości z `.env`.
Klucz API nigdy nie jest zwracany w odpowiedzi – panel dostaje tylko informację,
czy klucz jest ustawiony i skąd pochodzi.
"""

import base64
import hashlib
import os
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.catalog import (
    DEFAULT_PROVIDER,
    PROVIDERS_BY_KEY,
    ProviderOption,
    default_model,
)
from app.llm.factory import build_runtime_provider

if TYPE_CHECKING:
    from app.core.pipeline import VerificationService
    from app.store.db import Store

SETTING_KEY = "llm"
_ENV_KEEP = object()
_ENC_PREFIX = "enc:"


def _fernet_key(settings: Settings) -> bytes:
    salt = settings.id_hash_salt.get_secret_value().encode()
    raw = hashlib.sha256(b"llm_api_key:" + salt).digest()
    return base64.urlsafe_b64encode(raw)


def _encrypt(value: str | None, settings: Settings) -> str | None:
    if not value:
        return value
    from cryptography.fernet import Fernet
    return _ENC_PREFIX + Fernet(_fernet_key(settings)).encrypt(value.encode()).decode()


def _decrypt(value: str | None, settings: Settings) -> str | None:
    if not value:
        return value
    if not value.startswith(_ENC_PREFIX):
        return value  # backward compatible: wartość jeszcze niezaszyfrowana
    from cryptography.fernet import Fernet
    return Fernet(_fernet_key(settings)).decrypt(value[len(_ENC_PREFIX):].encode()).decode()


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    model: str
    base_url: str
    api_key: str | None = field(default=None, repr=False)
    price_input: float | None = None
    price_output: float | None = None
    json_mode: str = "json_object"

    @property
    def spec(self) -> ProviderOption:
        return PROVIDERS_BY_KEY[self.provider]

    @property
    def is_local(self) -> bool:
        return self.spec.is_local


def _catalog_prices(provider_key: str, model: str) -> tuple[float | None, float | None]:
    spec = PROVIDERS_BY_KEY.get(provider_key)
    if spec:
        for option in spec.models:
            if option.id == model:
                return option.price_input, option.price_output
    return None, None


def default_config(settings: Settings) -> LlmConfig:
    """Konfiguracja z `.env`, używana dopóki panel niczego nie zapisał."""
    provider_key = settings.llm_provider if settings.llm_provider in PROVIDERS_BY_KEY else DEFAULT_PROVIDER
    if settings.llm_provider == "anthropic":
        provider_key = "anthropic"
    model = settings.llm_model
    base_url = settings.llm_base_url
    option = default_model(provider_key)
    if option and not model:
        model, base_url = option.id, PROVIDERS_BY_KEY[provider_key].base_url
    if not model:
        model = option.id if option else ""
    if not base_url:
        base_url = PROVIDERS_BY_KEY[provider_key].base_url
    price_in, price_out = _catalog_prices(provider_key, model)
    if settings.llm_price_input_per_mtok is not None:
        price_in = settings.llm_price_input_per_mtok
    if settings.llm_price_output_per_mtok is not None:
        price_out = settings.llm_price_output_per_mtok
    return LlmConfig(
        provider=provider_key,
        model=model,
        base_url=base_url,
        api_key=None,
        price_input=price_in,
        price_output=price_out,
        json_mode=settings.llm_json_mode,
    )


def _as_optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def config_from_dict(raw: dict, settings: Settings) -> LlmConfig:
    base = default_config(settings)
    provider_key = str(raw.get("provider") or base.provider)
    if provider_key not in PROVIDERS_BY_KEY:
        provider_key = base.provider
    spec = PROVIDERS_BY_KEY[provider_key]
    option = default_model(provider_key)
    model = str(raw.get("model") or (option.id if option else base.model))
    base_url = str(raw.get("base_url") or spec.base_url)
    price_in = _as_optional_float(raw.get("price_input"))
    price_out = _as_optional_float(raw.get("price_output"))
    if price_in is None and price_out is None:
        price_in, price_out = _catalog_prices(provider_key, model)
    raw_key = raw.get("api_key")
    api_key = _decrypt(str(raw_key) if raw_key else None, settings)
    return LlmConfig(
        provider=provider_key,
        model=model,
        base_url=base_url,
        api_key=api_key,
        price_input=price_in,
        price_output=price_out,
        json_mode=str(raw.get("json_mode") or "json_object"),
    )


def load_config(store: "Store", settings: Settings) -> LlmConfig:
    raw = store.get_setting(SETTING_KEY)
    if not raw:
        return default_config(settings)
    return config_from_dict(raw, settings)


def save_config(
    store: "Store",
    config: LlmConfig,
    updated_by: str,
    settings: "Settings | None" = None,
) -> LlmConfig:
    stored_key = _encrypt(config.api_key, settings) if settings and config.api_key else config.api_key
    store.set_setting(
        SETTING_KEY,
        {
            "provider": config.provider,
            "model": config.model,
            "base_url": config.base_url,
            "api_key": stored_key,
            "price_input": config.price_input,
            "price_output": config.price_output,
            "json_mode": config.json_mode,
        },
        updated_by,
    )
    return config


def _env_api_key(settings: Settings, provider_key: str) -> str | None:
    candidates = {
        "deepseek": settings.llm_api_key,
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "gemini": settings.gemini_api_key,
        "openrouter": settings.openrouter_api_key,
    }
    secret = candidates.get(provider_key)
    if secret:
        return secret.get_secret_value()
    environment = {
        "deepseek": ("DEEPSEEK_API_KEY",),
        "openai": ("OPENAI_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "openrouter": ("OPENROUTER_API_KEY",),
    }.get(provider_key, ())
    for name in environment:
        value = os.environ.get(name)
        if value:
            return value
    return None


def resolve_api_key(settings: Settings, config: LlmConfig) -> tuple[str | None, str]:
    """Zwraca (klucz, źródło). Zapisany w panelu klucz ma pierwszeństwo przed .env."""
    if config.api_key:
        return config.api_key, "panel"
    env_key = _env_api_key(settings, config.provider)
    if env_key:
        return env_key, "env"
    return None, "none"


def key_hint(key: str | None) -> str | None:
    if not key:
        return None
    return f"••••{key[-4:]}" if len(key) > 4 else "••••"


def effective_prices(config: LlmConfig) -> tuple[float | None, float | None]:
    if config.price_input is None and config.price_output is None:
        return _catalog_prices(config.provider, config.model)
    return config.price_input, config.price_output


def build_for_config(
    settings: Settings,
    config: LlmConfig,
    *,
    use_env_key: bool = True,
) -> LLMProvider | None:
    key = config.api_key if config.api_key else (_env_api_key(settings, config.provider) if use_env_key else None)
    return build_runtime_provider(settings, config, key)


def public_settings(settings: Settings, config: LlmConfig) -> dict:
    key, source = resolve_api_key(settings, config)
    price_in, price_out = effective_prices(config)
    return {
        "provider": config.provider,
        "model": config.model,
        "base_url": config.base_url,
        "json_mode": config.json_mode,
        "price_input": price_in,
        "price_output": price_out,
        "api_key_set": key is not None,
        "api_key_source": source,
        "api_key_hint": key_hint(key),
        "requires_key": config.spec.requires_key,
        "is_local": config.is_local,
    }


def apply_config(
    service: "VerificationService",
    settings: Settings,
    config: LlmConfig,
) -> LLMProvider | None:
    provider = build_for_config(settings, config)
    service.set_provider(provider)
    service.set_price_override(effective_prices(config))
    return provider


def apply_stored_config(
    app,
    store: "Store",
    service: "VerificationService",
    settings: Settings,
) -> LlmConfig | None:
    """Stosuje wybór z panelu przy starcie. Brak wpisu = zostaje konfiguracja z `.env`."""
    if store.get_setting(SETTING_KEY) is None:
        return None
    config = load_config(store, settings)
    provider = apply_config(service, settings, config)
    app.state.llm_config = config
    app.state.llm_ready = provider is not None
    return config


def with_key(config: LlmConfig, api_key: str | None) -> LlmConfig:
    return replace(config, api_key=api_key or None)
