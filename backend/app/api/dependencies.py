"""Application container and FastAPI dependency providers."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.core.config import Settings
from app.db.base import Database
from app.db.repositories import SqlReportStorage, SqlReviewStorage
from app.engine.decision_engine import DecisionEngine
from app.reports.report_generator import ReportGenerator
from app.rules.registry import RuleRegistry
from app.services.cases import CaseScreeningService, CaseService
from app.services.documents import DocumentService
from app.services.file_store import FileStore
from app.services.report_service import ReportService
from app.services.review_service import HumanReviewService
from app.services.screening_service import ScreeningService


@dataclass
class Container:
    """Long-lived application components, built once per process."""

    settings: Settings
    db: Database
    registry: RuleRegistry
    engine: DecisionEngine
    reports: SqlReportStorage
    reviews: SqlReviewStorage
    generator: ReportGenerator
    files: FileStore
    cases: CaseService
    documents: DocumentService
    case_screening: CaseScreeningService
    screening: ScreeningService
    report_service: ReportService
    human_review: HumanReviewService

    @classmethod
    def build(cls, settings: Settings, *, inline_processing: bool = False) -> Container:
        db = Database(settings.database_url)
        db.migrate()
        registry = RuleRegistry(settings.ruleset_version)
        engine = DecisionEngine(
            registry, regulatory_validation_confirmed=settings.regulatory_validation_confirmed
        )
        reports = SqlReportStorage(db)
        reviews = SqlReviewStorage(db)
        generator = ReportGenerator()
        files = FileStore(settings.document_dir)
        return cls(
            settings=settings,
            db=db,
            registry=registry,
            engine=engine,
            reports=reports,
            reviews=reviews,
            generator=generator,
            files=files,
            cases=CaseService(db),
            documents=DocumentService(db, files, settings, inline=inline_processing),
            case_screening=CaseScreeningService(db, engine, reports),
            screening=ScreeningService(engine, reports, settings),
            report_service=ReportService(reports, generator),
            human_review=HumanReviewService(reports, reviews),
        )

    def startup(self) -> None:
        self.files.cleanup_temp()
        self.documents.recover_interrupted()
        self.documents.purge_expired()

    def shutdown(self) -> None:
        self.documents.shutdown()
        self.db.engine.dispose()


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


def get_rule_registry(request: Request) -> RuleRegistry:
    return get_container(request).registry


def get_screening_service(request: Request) -> ScreeningService:
    return get_container(request).screening


def get_report_service(request: Request) -> ReportService:
    return get_container(request).report_service


def get_human_review_service(request: Request) -> HumanReviewService:
    return get_container(request).human_review


def get_app_settings(request: Request) -> Settings:
    return get_container(request).settings
