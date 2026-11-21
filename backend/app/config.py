from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # --- model językowy (wymienny dostawca) ---
    # Domyślnie DeepSeek przez API zgodne z OpenAI. Identyfikator `deepseek-flash`
    # jest obecnie obsługiwany przez model DeepSeek-V4.1-Flash.
    llm_provider: Literal["openai_compatible", "anthropic", "none"] = "openai_compatible"
    llm_model: str = "deepseek-flash"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: SecretStr | None = None
    # DeepSeek przyjmuje tylko `json_object`; `json_schema` jest dla dostawców, którzy go obsługują.
    llm_json_mode: Literal["json_object", "json_schema"] = "json_object"
    llm_timeout_s: float = 60.0
    llm_extract_effort: str = "low"
    llm_assess_effort: str = "medium"
    anthropic_api_key: SecretStr | None = None
    # Ceny za 1 mln tokenów dla modeli spoza wbudowanej tabeli (app/llm/base.py).
    llm_price_input_per_mtok: float | None = None
    llm_price_output_per_mtok: float | None = None
    processing_location: str = (
        "Wyszukiwanie i baza: lokalnie na serwerze usługi. Model językowy: API dostawcy "
        "(domyślnie DeepSeek, dostawca z siedzibą w Chinach, poza EOG) – zmień LLM_BASE_URL i LLM_MODEL, "
        "aby przetwarzać w EOG lub lokalnie."
    )

    # --- wyszukiwanie ---
    embeddings: Literal["fastembed", "off"] = "fastembed"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    retrieval_top_k: int = 8
    archival_days: int = 365

    # --- weryfikacja ---
    max_claims: int = 4
    max_input_chars: int = 20000
    result_cache_hours: int = 24

    # --- bezpieczeństwo i prywatność ---
    admin_token: SecretStr | None = None
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    rate_limit_per_minute: int = 10
    retention_days: int = 30
    id_hash_salt: SecretStr = SecretStr("zmien-mnie-w-env")
    crawler_user_agent: str = "fact-check-research-bot/0.1"
    url_fetch_timeout_s: float = 10.0
    url_fetch_max_bytes: int = 2_000_000
    image_max_bytes: int = 5_000_000

    # --- pętla informacji ---
    case_loop_enabled: bool = True
    case_notify_threshold: int = 2
    moderator_webhook_url: str | None = None

    # --- demonstracyjny kanał SMS (symulator w interfejsie WWW) ---
    sms_mode: Literal["demo", "off"] = "demo"
    public_web_url: str = "http://localhost:3000"

    database_url: str = f"sqlite:///{DATA_DIR / 'prawdowid.db'}"
    corpus_dir: Path = DATA_DIR / "corpus"
    index_dir: Path = DATA_DIR / "index"
    catalog_path: Path = DATA_DIR / "sources.yaml"
    source_status_path: Path = DATA_DIR / "source_status.yaml"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
