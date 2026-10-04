"""
Shared pytest fixtures.

The test session uses an isolated temporary data directory and SQLite database so
tests never touch ./data. ``app_factory`` builds fresh applications with custom
settings and inline (synchronous) document processing.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

_SESSION_DIR = Path(tempfile.mkdtemp(prefix="ipo-tests-"))
os.environ["DATA_DIR"] = str(_SESSION_DIR / "data")
os.environ["DATABASE_URL"] = f"sqlite:///{_SESSION_DIR / 'data' / 'test.db'}"
for _var in ("API_KEY", "API_KEYS", "REPORT_DATABASE_URL"):
    os.environ.pop(_var, None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.models.company_data import CompanyData  # noqa: E402
from app.rules.registry import RuleRegistry  # noqa: E402
from tests.fixtures.company_data_factory import CompanyDataFactory  # noqa: E402

get_settings.cache_clear()


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:  # noqa: ARG001
    shutil.rmtree(_SESSION_DIR, ignore_errors=True)


@pytest.fixture
def company() -> CompanyData:
    """Default CompanyData with no failure under ruleset 2.0.0."""
    return CompanyDataFactory.create()


@pytest.fixture
def registry() -> RuleRegistry:
    """RuleRegistry bound to the current ruleset."""
    return RuleRegistry()


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[Callable[..., TestClient]]:
    """Build an isolated app (own DB + data dir) with inline document processing."""
    from app.main import create_app

    clients: list[TestClient] = []

    def make(**overrides: Any) -> TestClient:
        env = {
            "DATA_DIR": str(tmp_path / "data"),
            "DATABASE_URL": f"sqlite:///{tmp_path / 'app.db'}",
        }
        env.update({k: str(v) for k, v in overrides.items()})
        settings = Settings(**env)  # type: ignore[arg-type]
        client = TestClient(create_app(settings, inline_processing=True))
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)
