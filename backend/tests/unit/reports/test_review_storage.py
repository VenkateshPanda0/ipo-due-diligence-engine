from __future__ import annotations

from uuid import uuid4

from app.models.enums import IPOStatus
from app.models.human_review import HumanReviewRecord
from app.reports.review_storage import SQLiteReviewStorage


def test_sqlite_review_storage_persists_review_across_instances(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'reviews.db'}"
    report_id = uuid4()
    review = HumanReviewRecord(
        review_id=uuid4(),
        report_id=report_id,
        machine_status=IPOStatus.NEEDS_REVIEW,
    )

    first_storage = SQLiteReviewStorage(database_url)
    first_storage.save(review)
    second_storage = SQLiteReviewStorage(database_url)

    assert second_storage.get(review.review_id) == review
    assert second_storage.get_by_report_id(report_id) == review
