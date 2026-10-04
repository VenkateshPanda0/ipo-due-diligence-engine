"""Human review workflow service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.models.exceptions import InvalidStateError, ReportNotFoundError
from app.models.human_review import (
    HumanFinalDecision,
    HumanReviewRecord,
    HumanReviewStatus,
)
from app.reports.review_storage import ReviewStorage
from app.reports.storage import ReportStorage


class HumanReviewService:
    """Coordinate human review records for machine-generated reports."""

    def __init__(self, report_storage: ReportStorage, review_storage: ReviewStorage) -> None:
        self._report_storage = report_storage
        self._review_storage = review_storage

    def open_review(self, report_id: UUID, actor: str = "system") -> HumanReviewRecord:
        """Create or return the pending human review for a report."""
        report = self._report_storage.get(report_id)
        if report is None:
            raise ReportNotFoundError(report_id)

        existing = self._review_storage.get_by_report_id(report_id)
        if existing is not None:
            return existing

        review = HumanReviewRecord(
            report_id=report_id,
            machine_status=report.status,
        )
        self._save(review, actor)
        return review

    def get_review(self, review_id: UUID) -> HumanReviewRecord:
        """Return a review record by ID."""
        review = self._review_storage.get(review_id)
        if review is None:
            raise ReportNotFoundError(review_id)
        return review

    def complete_review(
        self,
        review_id: UUID,
        *,
        reviewer_name: str,
        final_decision: HumanFinalDecision,
        rationale: str,
        conditions: list[str] | None = None,
        actor: str = "system",
    ) -> HumanReviewRecord:
        """Record the human final decision. A completed review cannot be changed."""
        existing = self.get_review(review_id)
        if existing.status == HumanReviewStatus.COMPLETED:
            raise InvalidStateError(
                "human review",
                existing.status.value,
                "This review is already completed; decisions are immutable.",
            )
        completed = HumanReviewRecord(
            review_id=existing.review_id,
            report_id=existing.report_id,
            machine_status=existing.machine_status,
            status=HumanReviewStatus.COMPLETED,
            reviewer_name=reviewer_name,
            final_decision=final_decision,
            rationale=rationale,
            conditions=conditions or [],
            created_at=existing.created_at,
            completed_at=datetime.now(tz=UTC),
        )
        self._save(completed, actor)
        return completed

    def _save(self, review: HumanReviewRecord, actor: str) -> None:
        self._review_storage.save(review, actor=actor)

    def history(self, review_id: UUID) -> list[dict[str, object]]:
        history = getattr(self._review_storage, "history", None)
        return history(review_id) if callable(history) else []
