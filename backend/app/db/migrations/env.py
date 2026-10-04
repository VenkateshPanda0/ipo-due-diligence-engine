"""Alembic environment."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from app.db import models  # noqa: F401  (register tables)
from app.db.base import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = config.attributes.get("engine") or create_engine(
        config.get_main_option("sqlalchemy.url") or ""
    )
    with engine.begin() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
