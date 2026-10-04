"""Engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _sqlite_path(url: str) -> Path | None:
    if url.startswith("sqlite:///") and ":memory:" not in url:
        return Path(url.removeprefix("sqlite:///"))
    return None


def make_engine(url: str) -> Engine:
    """Create an engine. SQLite gets foreign keys, WAL and a busy timeout."""
    path = _sqlite_path(url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn: Any, _record: Any) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            if path is not None:
                cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

    return engine


class Database:
    """Owns an engine and a session factory."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = make_engine(url)
        self._factory = sessionmaker(self.engine, expire_on_commit=False, future=True)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transactional scope: commit on success, roll back on error."""
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def migrate(self) -> None:
        """Apply all Alembic migrations (idempotent)."""
        from app.db.migrate import upgrade_to_head

        upgrade_to_head(self.engine)

    def ping(self) -> bool:
        """Return True if the database answers a trivial query."""
        try:
            with self.engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return True
        except Exception:
            return False
