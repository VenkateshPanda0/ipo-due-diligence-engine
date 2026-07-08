from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import IPOStatus
from app.models.human_review import (
    HumanFinalDecision,
    HumanReviewRecord,
    HumanReviewStatus,
)


def test_pending_human_review_does_not_require_final_decision() -> None:
    review = HumanReviewRecord(report_id=uuid4(), machine_status=IPOStatus.ELIGIBLE)

    assert review.status == HumanReviewStatus.PENDING
    assert review.final_decision is None


def test_completed_human_review_requires_signoff_fields() -> None:
    with pytest.raises(ValidationError):
        HumanReviewRecord(
            report_id=uuid4(),
            machine_status=IPOStatus.ELIGIBLE,
            status=HumanReviewStatus.COMPLETED,
            final_decision=HumanFinalDecision.PROCEED,
        )
