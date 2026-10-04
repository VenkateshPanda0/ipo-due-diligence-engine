"""Human review models for analyst sign-off workflows.

The deterministic engine produces a machine assessment. These models record
the separate human decision that can approve, reject, or request more
information. They contain no parser, API, or rule logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import IPOStatus


class HumanReviewStatus(str, Enum):
    """Lifecycle state for a human review record."""

    PENDING = "pending"
    COMPLETED = "completed"


class HumanFinalDecision(str, Enum):
    """Final disposition selected by a human reviewer."""

    PROCEED = "proceed"
    DO_NOT_PROCEED = "do_not_proceed"
    NEEDS_MORE_INFORMATION = "needs_more_information"


class HumanReviewRecord(BaseModel):
    """Human sign-off record attached to a machine-generated report."""

    model_config = ConfigDict(frozen=True)

    review_id: UUID = Field(default_factory=uuid4)
    report_id: UUID
    machine_status: IPOStatus
    status: HumanReviewStatus = HumanReviewStatus.PENDING
    reviewer_name: str | None = None
    final_decision: HumanFinalDecision | None = None
    rationale: str | None = None
    conditions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_completed_review(self) -> HumanReviewRecord:
        """Require reviewer, decision, and rationale when review is completed."""
        if self.status == HumanReviewStatus.COMPLETED:
            missing = [
                field_name
                for field_name, value in (
                    ("reviewer_name", self.reviewer_name),
                    ("final_decision", self.final_decision),
                    ("rationale", self.rationale),
                    ("completed_at", self.completed_at),
                )
                if value in (None, "")
            ]
            if missing:
                raise ValueError(f"Completed human review is missing required fields: {missing}")
        return self
