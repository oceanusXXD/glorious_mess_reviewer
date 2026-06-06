"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the review service."""

    model_config = SettingsConfigDict(
        env_prefix="GLORIOUS_MESS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "glorious_mess_reviewer"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    debug: bool = False
    prompt_version: str = "v1"

    default_model: str = "gpt-4o-mini"
    provider_backend: Literal["openai", "mock"] = "openai"
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GLORIOUS_MESS_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    openai_base_url: str | None = None
    openai_api_style: Literal["responses", "chat_completions"] = "responses"
    default_temperature: float = Field(default=0.2, ge=0.0, le=1.5)
    request_timeout_seconds: float = Field(default=60.0, gt=0)
    provider_max_retries: int = Field(default=1, ge=0, le=5)

    database_path: Path = Path("glorious_mess_reviews.db")
    store_raw_agent_outputs: bool = True
    log_prompt_text: bool = False
    minimum_reviewable_characters: int = Field(default=1200, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object."""

    return Settings()
