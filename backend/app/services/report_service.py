"""Report retrieval and formatting service."""

from __future__ import annotations

from uuid import UUID

from app.models.exceptions import ReportNotFoundError
from app.reports.report_generator import ReportGenerator
from app.reports.storage import ReportStorage


class ReportService:
    """Retrieve stored reports and render them in requested formats."""

    def __init__(self, storage: ReportStorage, generator: ReportGenerator) -> None:
        self._storage = storage
        self._generator = generator

    def get_report(self, report_id: UUID, format: str = "json") -> str:
        """Return a rendered report or raise ReportNotFoundError."""
        report = self._storage.get(report_id)
        if report is None:
            raise ReportNotFoundError(report_id)
        return self._generator.generate(report, format)

    def report_exists(self, report_id: UUID) -> bool:
        """Return whether the report exists."""
        return self._storage.exists(report_id)
