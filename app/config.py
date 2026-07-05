"""Centralized application configuration.

Loads all runtime configuration from environment variables (via a `.env`
file in development) using pydantic-settings. Every other module in the
application should import `settings` from here rather than reading
`os.environ` directly, so configuration stays in a single, typed location.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
PROMPTS_DIR: Path = Path(__file__).resolve().parent / "prompts"


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables.

    Attributes:
        mistral_api_key: API key for the Mistral AI service.
        mistral_model: Mistral model identifier used for generation.
        cognee_api_key: API key for Cognee Cloud.
        cognee_base_url: Base URL for the Cognee Cloud REST API.
        cognee_dataset: Name of the Cognee dataset used to namespace memories.
        app_env: Current application environment (e.g. "development").
        log_level: Loguru/standard logging level name.
        story_max_words: Soft cap on generated story length, in words.
        memory_retrieval_limit: Max number of memories to retrieve per event.
        request_timeout_seconds: Timeout applied to outbound HTTP requests.
    """

    mistral_api_key: str
    mistral_model: str = "mistral-large-latest"

    cognee_api_key: str
    cognee_base_url: str = "https://api.cognee.ai"
    cognee_dataset: str = "memory_narrative_engine"

    app_env: str = "development"
    log_level: str = "INFO"

    story_max_words: int = 150
    memory_retrieval_limit: int = 8
    request_timeout_seconds: int = 30

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide `Settings` instance.

    Using `lru_cache` ensures the `.env` file and environment are parsed
    only once, and every caller receives the same settings object.

    Returns:
        The application's `Settings` instance.
    """

    return Settings()


settings: Settings = get_settings()
