"""Legacy (API v0) one-shot screening: JSON or a single PDF, no case."""

from __future__ import annotations

from app.core.config import Settings
from app.engine.decision_engine import DecisionEngine
from app.intelligence.ingest import validate_pdf
from app.intelligence.pipeline import PipelineConfig, run_pipeline
from app.models.company_data import CompanyData
from app.models.exceptions import UnsupportedDocumentError
from app.models.ipo_report import IPOReport
from app.reports.storage import ReportStorage


class ScreeningService:
    """Evaluate a CompanyData snapshot (or an uploaded PDF) and persist the report."""

    def __init__(self, engine: DecisionEngine, storage: ReportStorage, settings: Settings) -> None:
        self._engine = engine
        self._storage = storage
        self._settings = settings

    def screen_json(self, company: CompanyData) -> IPOReport:
        report = self._engine.evaluate(company)
        self._storage.save(report.report_id, report)
        return report

    def screen_pdf(self, filename: str, content: bytes) -> IPOReport:
        """Validate, extract and screen one PDF synchronously (call from a worker thread)."""
        info = validate_pdf(
            content,
            filename,
            max_bytes=self._settings.max_upload_size_bytes,
            max_pages=self._settings.max_pdf_pages,
        )
        result = run_pipeline(
            content,
            filename=info.display_name,
            document_id=info.sha256,
            company_name=info.display_name.removesuffix(".pdf"),
            config=PipelineConfig(
                self._settings.ocr_enabled,
                self._settings.max_ocr_pages,
                self._settings.ocr_dpi,
                self._settings.processing_timeout_s,
            ),
        )
        if result.doc_type == "unknown" and result.tables_found == 0:
            raise UnsupportedDocumentError(info.display_name)
        company = CompanyData.model_validate(result.payload)
        report = self._engine.evaluate(company, document_ids=[info.sha256])
        self._storage.save(report.report_id, report)
        return report
