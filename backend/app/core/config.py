"""Application settings loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets are only read from the environment."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"], alias="CORS_ORIGINS"
    )

    # Authentication. API_KEYS entries: "<user_id>|<role>|<key or sha256=hex>", comma separated.
    # Roles: viewer, analyst, reviewer, admin. API_KEY (legacy) maps to an analyst principal.
    api_key: str | None = Field(default=None, alias="API_KEY")
    api_keys: str | None = Field(default=None, alias="API_KEYS")

    database_url: str = Field(  # type: ignore[pydantic-alias]  # env alias fallback
        default="sqlite:///./data/ipo_due_diligence.db",
        validation_alias=AliasChoices("DATABASE_URL", "REPORT_DATABASE_URL"),
    )
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")

    ruleset_version: str = Field(default="2.0.0", alias="RULESET_VERSION")
    regulatory_validation_confirmed: bool = Field(
        default=False, alias="REGULATORY_VALIDATION_CONFIRMED"
    )
    regulatory_validation_reference: str | None = Field(
        default=None, alias="REGULATORY_VALIDATION_REFERENCE"
    )

    # Document processing limits.
    max_upload_size_mb: int = Field(default=50, ge=1, le=500, alias="MAX_UPLOAD_SIZE_MB")
    max_pdf_pages: int = Field(default=1500, ge=1, alias="MAX_PDF_PAGES")
    max_ocr_pages: int = Field(default=60, ge=0, alias="MAX_OCR_PAGES")
    ocr_enabled: bool = Field(default=True, alias="OCR_ENABLED")
    ocr_dpi: int = Field(default=200, ge=72, le=400, alias="OCR_DPI")
    processing_timeout_s: int = Field(default=900, ge=10, alias="PROCESSING_TIMEOUT_S")
    worker_threads: int = Field(default=2, ge=1, le=16, alias="WORKER_THREADS")
    retain_documents: bool = Field(default=True, alias="RETAIN_DOCUMENTS")
    retention_days: int = Field(default=90, ge=1, alias="RETENTION_DAYS")
    rate_limit_per_minute: int = Field(default=30, ge=1, alias="UPLOAD_RATE_LIMIT_PER_MINUTE")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: Any) -> Any:
        """Accept a comma-separated string as well as a list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key or self.api_keys)

    @property
    def document_dir(self) -> Path:
        return self.data_dir / "documents"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
