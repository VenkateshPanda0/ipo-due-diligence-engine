"""Screening service orchestration."""

from __future__ import annotations

from app.engine.decision_engine import DecisionEngine
from app.models.company_data import CompanyData
from app.models.ipo_report import IPOReport
from app.reports.storage import ReportStorage
from app.rules.registry import RuleRegistry
from app.services.extraction_service import ExtractionService


class ScreeningService:
    """Coordinate JSON/PDF screening workflows."""

    def __init__(
        self,
        registry: RuleRegistry,
        storage: ReportStorage,
        extraction_service: ExtractionService | None = None,
    ) -> None:
        self._decision_engine = DecisionEngine(registry)
        self._storage = storage
        self._extraction_service = extraction_service or ExtractionService()

    def screen_json(self, company: CompanyData) -> IPOReport:
        """Evaluate CompanyData and persist the generated report."""
        report = self._decision_engine.evaluate(company)
        self._storage.save(report.report_id, report)
        return report

    def screen_pdf(self, filename: str, content: bytes) -> IPOReport:
        """Extract CompanyData from a PDF-like upload and evaluate it."""
        company = self._extraction_service.extract_company_data(filename, content)
        return self.screen_json(company)
