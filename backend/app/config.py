from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # --- LLM Providers ---
    # DeepSeek (for final fake news verdict)
    llm_provider: Literal["openai_compatible", "anthropic", "none"] = "openai_compatible"
    llm_model: str = "deepseek-flash"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: SecretStr | None = None
    llm_json_mode: Literal["json_object", "json_schema"] = "json_object"
    llm_timeout_s: float = 60.0

    # Bielik 4.5B Instruct (for keyword extraction) - typically served via Ollama/vLLM
    bielik_base_url: str = "http://localhost:11434/v1"  # Ollama OpenAI-compatible endpoint
    bielik_model: str = "llama3.2:3b"
    bielik_api_key: SecretStr | None = None
    bielik_timeout_s: float = 120.0

    # Doprecyzowanie: który model decyduje, czy dopytać użytkownika ("llm" = główny model, np. DeepSeek;
    # "bielik"; "off" = tylko reguła zbyt krótkiego tekstu) i ile razy najwyżej dopytujemy.
    clarification_model: Literal["llm", "bielik", "off"] = "llm"
    clarification_max_rounds: int = 2

    # Google Fact Check Tools API
    google_factcheck_api_key: SecretStr | None = None

    # Costs (per 1M tokens)
    llm_price_input_per_mtok: float | None = None
    llm_price_output_per_mtok: float | None = None

    processing_location: str = (
        "Wyszukiwanie i baza: lokalnie na serwerze usługi. Model językowy: API dostawcy "
        "(domyślnie DeepSeek, dostawca z siedzibą w Chinach, poza EOG) – zmień LLM_BASE_URL i LLM_MODEL, "
        "aby przetwarzać w EOG lub lokalnie. Bielik działa lokalnie (Ollama/vLLM)."
    )

    # --- Security & Privacy ---
    admin_token: SecretStr | None = None
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    rate_limit_per_minute: int = 10
    retention_days: int = 30
    id_hash_salt: SecretStr = SecretStr("zmien-mnie-w-env")
    crawler_user_agent: str = "fact-check-research-bot/0.1"
    url_fetch_timeout_s: float = 10.0
    url_fetch_max_bytes: int = 2_000_000
    image_max_bytes: int = 10 * 1024 * 1024  # tyle samo co limit we frontendzie (10 MB)

    # --- Odwrotne wyszukiwanie obrazu (PicImageSearch, bez kluczy API) ---
    # Dostępne: yandex, tineye, bing (bing domyślnie wyłączony – nie działa w PicImageSearch 3.12.11).
    image_search_engines: str = "yandex,tineye"
    image_search_timeout_s: float = 25.0
    image_compare_max_candidates: int = 10
    image_candidate_max_bytes: int = 8_000_000
    image_cache_hours: int = 24

    database_url: str = f"sqlite:///{DATA_DIR / 'prawdowid.db'}"

    @property
    def image_engine_list(self) -> list[str]:
        return [e.strip().lower() for e in self.image_search_engines.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()