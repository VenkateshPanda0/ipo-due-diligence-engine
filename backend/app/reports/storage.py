"""Report storage protocol and an in-memory implementation (tests / embedding).

The production implementation is ``app.db.repositories.SqlReportStorage``.
Reports are immutable snapshots: once saved they are never re-evaluated or edited.
"""

from __future__ import annotations

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
    """Thread-safe in-memory report storage."""

    def __init__(self) -> None:
        self._reports: dict[UUID, IPOReport] = {}
        self._lock = RLock()

    def save(self, report_id: UUID, report: IPOReport) -> None:
        with self._lock:
            if report_id in self._reports:
                raise ValueError("Reports are immutable; report_id already exists.")
            self._reports[report_id] = report

    def get(self, report_id: UUID) -> IPOReport | None:
        with self._lock:
            return self._reports.get(report_id)

    def exists(self, report_id: UUID) -> bool:
        with self._lock:
            return report_id in self._reports
