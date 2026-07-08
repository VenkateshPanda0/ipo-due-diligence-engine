"""FastAPI dependency providers."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.reports.report_generator import ReportGenerator
from app.reports.review_storage import ReviewStorage, SQLiteReviewStorage
from app.reports.storage import ReportStorage, SQLiteReportStorage
from app.rules.registry import RuleRegistry
from app.services.report_service import ReportService
from app.services.review_service import HumanReviewService
from app.services.screening_service import ScreeningService


@lru_cache(maxsize=1)
def get_rule_registry() -> RuleRegistry:
    """Return singleton rule registry."""
    return RuleRegistry()


@lru_cache(maxsize=1)
def get_report_storage() -> ReportStorage:
    """Return singleton report storage."""
    return SQLiteReportStorage(get_settings().report_database_url)


@lru_cache(maxsize=1)
def get_review_storage() -> ReviewStorage:
    """Return singleton human review storage."""
    return SQLiteReviewStorage(get_settings().report_database_url)


@lru_cache(maxsize=1)
def get_report_generator() -> ReportGenerator:
    """Return singleton report generator."""
    return ReportGenerator()


def get_screening_service() -> ScreeningService:
    """Return screening service."""
    return ScreeningService(get_rule_registry(), get_report_storage())


def get_report_service() -> ReportService:
    """Return report service."""
    return ReportService(get_report_storage(), get_report_generator())


def get_human_review_service() -> HumanReviewService:
    """Return human review service."""
    return HumanReviewService(get_report_storage(), get_review_storage())


def get_app_settings() -> Settings:
    """Return application settings."""
    return get_settings()
