"""Storage abstraction for human review records."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import UUID

from app.models.human_review import HumanReviewRecord


class ReviewStorage(Protocol):
    """Persistence contract for human review records."""

    def save(self, review: HumanReviewRecord) -> None:
        """Persist a review record."""

    def get(self, review_id: UUID) -> HumanReviewRecord | None:
        """Return a review by ID, or None when absent."""

    def get_by_report_id(self, report_id: UUID) -> HumanReviewRecord | None:
        """Return the review for a report, or None when absent."""


class InMemoryReviewStorage:
    """Thread-safe in-memory storage for human review records."""

    def __init__(self) -> None:
        self._reviews: dict[UUID, HumanReviewRecord] = {}
        self._review_by_report: dict[UUID, UUID] = {}
        self._lock = RLock()

    def save(self, review: HumanReviewRecord) -> None:
        """Persist or overwrite a review record."""
        with self._lock:
            self._reviews[review.review_id] = review
            self._review_by_report[review.report_id] = review.review_id

    def get(self, review_id: UUID) -> HumanReviewRecord | None:
        """Return a review by ID, or None when absent."""
        with self._lock:
            return self._reviews.get(review_id)

    def get_by_report_id(self, report_id: UUID) -> HumanReviewRecord | None:
        """Return the review for a report, or None when absent."""
        with self._lock:
            review_id = self._review_by_report.get(report_id)
            if review_id is None:
                return None
            return self._reviews.get(review_id)


class SQLiteReviewStorage:
    """SQLite-backed human review storage for local production deployments."""

    def __init__(self, database_url: str) -> None:
        self._path = self._path_from_url(database_url)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def save(self, review: HumanReviewRecord) -> None:
        """Persist or overwrite a review record."""
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO human_reviews (review_id, report_id, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(review_id) DO UPDATE SET
                    report_id = excluded.report_id,
                    payload = excluded.payload
                """,
                (str(review.review_id), str(review.report_id), review.model_dump_json()),
            )

    def get(self, review_id: UUID) -> HumanReviewRecord | None:
        """Return a review by ID, or None when absent."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM human_reviews WHERE review_id = ?",
                (str(review_id),),
            ).fetchone()
        if row is None:
            return None
        return HumanReviewRecord.model_validate_json(str(row["payload"]))

    def get_by_report_id(self, report_id: UUID) -> HumanReviewRecord | None:
        """Return the review for a report, or None when absent."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM human_reviews WHERE report_id = ?",
                (str(report_id),),
            ).fetchone()
        if row is None:
            return None
        return HumanReviewRecord.model_validate_json(str(row["payload"]))

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS human_reviews (
                    review_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL UNIQUE,
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
