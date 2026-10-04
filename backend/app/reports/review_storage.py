"""Human-review storage protocol and an in-memory implementation (tests / embedding).

The production implementation is ``app.db.repositories.SqlReviewStorage`` (append-only).
"""

from __future__ import annotations

from threading import RLock
from typing import Protocol
from uuid import UUID

from app.models.human_review import HumanReviewRecord, HumanReviewStatus


class ReviewStorage(Protocol):
    """Persistence contract for human review records."""

    def save(self, review: HumanReviewRecord, actor: str = "system") -> None:
        """Persist a new review or record its (single, immutable) completion."""

    def get(self, review_id: UUID) -> HumanReviewRecord | None:
        """Return a review by ID."""

    def get_by_report_id(self, report_id: UUID) -> HumanReviewRecord | None:
        """Return the review attached to a report."""


class InMemoryReviewStorage:
    """Thread-safe in-memory review storage that also refuses re-completion."""

    def __init__(self) -> None:
        self._reviews: dict[UUID, HumanReviewRecord] = {}
        self._lock = RLock()

    def save(self, review: HumanReviewRecord, actor: str = "system") -> None:
        with self._lock:
            existing = self._reviews.get(review.review_id)
            if existing is not None and existing.status == HumanReviewStatus.COMPLETED:
                raise ValueError("Review already completed; decisions are immutable.")
            self._reviews[review.review_id] = review

    def get(self, review_id: UUID) -> HumanReviewRecord | None:
        with self._lock:
            return self._reviews.get(review_id)

    def get_by_report_id(self, report_id: UUID) -> HumanReviewRecord | None:
        with self._lock:
            return next((r for r in self._reviews.values() if r.report_id == report_id), None)
