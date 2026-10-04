"""Programmatic Alembic entry points (no alembic.ini needed)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

_SCRIPT_DIR = Path(__file__).parent / "migrations"


def alembic_config(engine: Engine | None = None, url: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_SCRIPT_DIR))
    if url:
        cfg.set_main_option("sqlalchemy.url", url)
    if engine is not None:
        cfg.attributes["engine"] = engine
    return cfg


def upgrade_to_head(engine: Engine) -> None:
    """Apply all pending migrations using the given engine."""
    command.upgrade(alembic_config(engine), "head")
