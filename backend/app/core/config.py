"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for API and services."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    api_key: str | None = Field(default=None, alias="API_KEY")
    report_database_url: str = Field(
        default="sqlite:///./data/ipo_due_diligence.db",
        alias="REPORT_DATABASE_URL",
    )
    ruleset_version: str = Field(default="1.0.0", alias="RULESET_VERSION")
    regulatory_validation_confirmed: bool = Field(
        default=False,
        alias="REGULATORY_VALIDATION_CONFIRMED",
    )
    regulatory_validation_reference: str | None = Field(
        default=None,
        alias="REGULATORY_VALIDATION_REFERENCE",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
