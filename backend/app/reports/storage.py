"""
backend/app/reports/storage.py

Storage abstraction for completed IPOReport objects.

The v1 implementation is in-memory and thread-safe. It deliberately contains
no rule, parser, API, or report rendering logic.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import UUID

from app.models.ipo_report import IPOReport


class ReportStorage(Protocol):
    """Persistence contract for completed IPO reports."""

    def save(self, report_id: UUID, report: IPOReport) -> None:
        """Persist a report by ID."""

    def get(self, report_id: UUID) -> IPOReport | None:
        """Return a report by ID, or None when absent."""

    def exists(self, report_id: UUID) -> bool:
        """Return whether the report ID exists."""


class InMemoryReportStorage:
    """Thread-safe in-memory report storage for v1."""

    def __init__(self) -> None:
        self._reports: dict[UUID, IPOReport] = {}
        self._lock = RLock()

    def save(self, report_id: UUID, report: IPOReport) -> None:
        """Persist or overwrite a report by ID."""
        with self._lock:
            self._reports[report_id] = report

    def get(self, report_id: UUID) -> IPOReport | None:
        """Return a report by ID, or None when absent."""
        with self._lock:
            return self._reports.get(report_id)

    def exists(self, report_id: UUID) -> bool:
        """Return whether the report ID exists."""
        with self._lock:
            return report_id in self._reports


class SQLiteReportStorage:
    """SQLite-backed report storage for local production deployments."""

    def __init__(self, database_url: str) -> None:
        self._path = self._path_from_url(database_url)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def save(self, report_id: UUID, report: IPOReport) -> None:
        """Persist or overwrite a report by ID."""
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reports (report_id, payload)
                VALUES (?, ?)
                ON CONFLICT(report_id) DO UPDATE SET payload = excluded.payload
                """,
                (str(report_id), report.model_dump_json()),
            )

    def get(self, report_id: UUID) -> IPOReport | None:
        """Return a report by ID, or None when absent."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM reports WHERE report_id = ?",
                (str(report_id),),
            ).fetchone()
        if row is None:
            return None
        return IPOReport.model_validate_json(str(row["payload"]))

    def exists(self, report_id: UUID) -> bool:
        """Return whether the report ID exists."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM reports WHERE report_id = ?",
                (str(report_id),),
            ).fetchone()
        return row is not None

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _path_from_url(database_url: str) -> Path:
        if not database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// REPORT_DATABASE_URL values are currently supported")
        return Path(database_url.removeprefix("sqlite:///"))
