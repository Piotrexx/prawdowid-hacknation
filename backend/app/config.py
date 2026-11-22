from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# Wersja polityki prywatności, na którą zbieramy zgodę. Zmiana wersji = ponowne pytanie.
PRIVACY_POLICY_VERSION = "2026-11-21"


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
    # Klucze pozostałych dostawców wybieranych w panelu (model można zmienić bez restartu).
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None

    # --- Bielik: lokalny polski model do ekstrakcji słów kluczowych ---
    # Ollama/vLLM, API zgodne z OpenAI. Bielik 4.5B v3.0 Instruct jest w bibliotece Ollamy
    # pod nazwą `SpeakLeash/bielik-4.5b-v3.0-instruct`; nie ma tagu `latest`, więc podajemy
    # kwantyzację wprost (Q8_0 ≈ 5,1 GB, alternatywa FP16 ≈ 9,5 GB).
    bielik_base_url: str = "http://localhost:11434/v1"
    bielik_model: str = "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
    bielik_api_key: SecretStr | None = None
    bielik_timeout_s: float = 120.0
    # Bielik na CPU to najwolniejszy etap: odpowiedź ze słowami kluczowymi ma zwykle 75–150 tokenów.
    bielik_max_tokens: int = 256
    # Ile najdłużej czekamy na słowa kluczowe od początku sprawdzenia; potem korzystamy z zapytań z twierdzeń.
    bielik_keywords_timeout_s: float = 20.0

    # --- Google Fact Check Tools API (kontekst wspierający) ---
    google_factcheck_api_key: SecretStr | None = None
    factcheck_timeout_s: float = 30.0

    # Ceny za 1 mln tokenów dla modeli spoza wbudowanej tabeli (app/llm/base.py).
    llm_price_input_per_mtok: float | None = None
    llm_price_output_per_mtok: float | None = None
    processing_location: str = (
        "Wyszukiwanie, baza i transkrypcja nagrań: lokalnie na serwerze usługi. "
        "Model językowy: API dostawcy (domyślnie DeepSeek, dostawca z siedzibą w Chinach, poza EOG) – "
        "zmień LLM_BASE_URL i LLM_MODEL, aby przetwarzać w EOG lub lokalnie. Bielik działa lokalnie."
    )

    # --- wyszukiwanie semantyczne (PostgreSQL + pgvector) ---
    embedding_backend: Literal["fastembed", "none"] = "fastembed"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    embedding_cache_dir: str | None = None
    retrieval_top_k: int = 6
    retrieval_candidates: int = 20
    retrieval_min_similarity: float = 0.58
    retrieval_strong_similarity: float = 0.82
    retrieval_max_age_days: int | None = None
    retrieval_max_per_source: int = 2

    # --- weryfikacja ---
    max_claims: int = 4
    # Ile razy najwyżej dopytujemy użytkownika, zanim sprawdzimy treść w obecnej postaci.
    clarification_max_rounds: int = 2
    max_input_chars: int = 20000
    result_cache_hours: int = 24
    archival_days: int = 365

    # --- multimodalność ---
    image_max_bytes: int = 5_000_000
    audio_max_bytes: int = 10_000_000
    audio_max_seconds: int = 120
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_cache_dir: str | None = None

    # --- konta moderatorów ---
    # Pierwsze konto superużytkownika powstaje przy starcie z tych wartości.
    # Bez hasła hasło startowe zostanie wygenerowane i jednorazowo zapisane w logu.
    moderator_bootstrap_email: str | None = None
    moderator_bootstrap_password: SecretStr | None = None
    moderator_bootstrap_name: str = "Superużytkownik"
    moderator_session_hours: int = 12

    # --- powiadomienia (Discord / e-mail / Web Push) ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    # Adres panelu używany w treści powiadomień i w powiadomieniach push.
    public_base_url: str = "http://localhost:3000"
    # Klucze VAPID do Web Push. Bez nich para kluczy powstaje przy pierwszym starcie
    # i jest zapisywana w tabeli app_settings.
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str = "mailto:moderatorzy@prawdowid.pl"

    # --- bezpieczeństwo i prywatność ---
    admin_token: SecretStr | None = None
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    rate_limit_per_minute: int = 10
    retention_days: int = 30
    id_hash_salt: SecretStr = SecretStr("zmien-mnie-w-env")
    crawler_user_agent: str = "fact-check-research-bot/0.1"
    url_fetch_timeout_s: float = 10.0
    url_fetch_max_bytes: int = 2_000_000
    privacy_policy_version: str = PRIVACY_POLICY_VERSION

    # --- Odwrotne wyszukiwanie obrazu (PicImageSearch, bez kluczy API) ---
    # Dostępne: yandex, tineye, bing (bing domyślnie wyłączony – nie działa w PicImageSearch 3.12.11).
    image_search_engines: str = "yandex,tineye"
    image_search_timeout_s: float = 25.0
    image_compare_max_candidates: int = 10
    image_candidate_max_bytes: int = 8_000_000
    image_cache_hours: int = 24

    # --- kontrolowana archiwizacja materiału ---
    archive_enabled: bool = True
    archive_max_chars: int = 2000
    archive_retention_days: int = 30
    archive_legal_basis: str = (
        "Archiwizacja na wyraźne żądanie użytkownika, w celu umożliwienia weryfikacji "
        "i audytu; przechowywany jest tylko krótki fragment i metadane."
    )

    # --- pętla informacji ---
    case_loop_enabled: bool = True
    case_notify_threshold: int = 2
    moderator_webhook_url: str | None = None

    # --- mapa wydarzeń (graf zgłoszeń i incydentów) ---
    event_graph_enabled: bool = True
    # Linkowanie w tle nie wydłuża odpowiedzi użytkownikowi. W testach wyłączone,
    # żeby wynik był deterministyczny.
    event_graph_async: bool = True
    # Kwalifikator LLM ocenia tylko pary w szarej strefie. Domyślnie wyłączony,
    # bo każde wywołanie kosztuje i wysyła do dostawcy treść starszych zgłoszeń.
    event_llm_qualifier_enabled: bool = False
    event_llm_accept_confidence: float = 0.7
    event_link_window_days: int = 90
    event_link_candidates: int = 8
    # Progi dla podobieństwa semantycznego (cosine) i zastępczego leksykalnego.
    event_link_auto_similarity: float = 0.84
    event_link_review_similarity: float = 0.68
    event_link_auto_lexical: float = 0.5
    event_link_review_lexical: float = 0.3
    # Publiczna mapa pokazuje wyłącznie zagregowane wydarzenia z co najmniej tyloma
    # zaakceptowanymi zgłoszeniami (k-anonimowość).
    event_public_min_members: int = 3
    event_public_limit: int = 300
    event_graph_limit: int = 500
    event_rebuild_limit: int = 500

    # --- webhook do powiadamiania o każdej nowej analizie fact-check ---
    fact_check_webhook_url: str | None = None

    # --- baza danych ---
    database_url: str = "postgresql+psycopg://prawdowid:prawdowid@localhost:5432/prawdowid"

    # --- ingest źródeł ---
    ingest_max_per_source: int = 10
    ingest_timeout_s: float = 20.0
    ingest_request_delay_s: float = 1.0
    ingest_cache_dir: str | None = None

    @property
    def image_engine_list(self) -> list[str]:
        return [e.strip().lower() for e in self.image_search_engines.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
