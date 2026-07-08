"""API response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import IPOStatus, RuleCategory, Verdict
from app.models.human_review import HumanFinalDecision, HumanReviewRecord, HumanReviewStatus
from app.models.ipo_report import EligibilityProgress, IPOReport
from app.models.rule_result import RuleMetadata, RuleResult


class ErrorDetail(BaseModel):
    """Standard error envelope body."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: ErrorDetail


class RuleResultSchema(BaseModel):
    """Serializable rule result response."""

    model_config = ConfigDict(from_attributes=True)

    rule_id: str
    verdict: Verdict
    category: RuleCategory
    regulation_reference: str
    description: str
    required_value: str
    actual_value: str | None
    gap: str | None
    explanation: str
    evaluated_at: datetime
    source_citation: dict[str, Any] | None

    @classmethod
    def from_domain(cls, result: RuleResult) -> RuleResultSchema:
        """Create API schema from domain RuleResult."""
        citation = (
            result.source_citation.model_dump(mode="json")
            if result.source_citation is not None
            else None
        )
        return cls(
            rule_id=result.rule_id,
            verdict=result.verdict,
            category=result.category,
            regulation_reference=result.regulation_reference,
            description=result.description,
            required_value=result.required_value,
            actual_value=result.actual_value,
            gap=result.gap,
            explanation=result.explanation,
            evaluated_at=result.evaluated_at,
            source_citation=citation,
        )


class ScreeningResponse(BaseModel):
    """Response returned by POST /screen/json."""

    report_id: UUID
    status: IPOStatus
    company_name: str
    mandatory_progress: EligibilityProgress
    advisory_progress: EligibilityProgress
    mandatory_results: list[RuleResultSchema]
    advisory_results: list[RuleResultSchema]
    gap_analysis: list[dict[str, Any]]
    observations: list[str]
    ruleset_version: str
    evaluated_at: datetime
    machine_assessment_only: bool = True
    human_review_required: bool = True
    decision_authority: str = "human_reviewer"

    @classmethod
    def from_report(cls, report: IPOReport) -> ScreeningResponse:
        """Create API response from IPOReport."""
        return cls(
            report_id=report.report_id,
            status=report.status,
            company_name=report.company_name,
            mandatory_progress=report.mandatory_progress,
            advisory_progress=report.advisory_progress,
            mandatory_results=[
                RuleResultSchema.from_domain(result) for result in report.mandatory_results
            ],
            advisory_results=[
                RuleResultSchema.from_domain(result) for result in report.advisory_results
            ],
            gap_analysis=[item.model_dump(mode="json") for item in report.gap_analysis],
            observations=report.observations,
            ruleset_version=report.ruleset_version.version,
            evaluated_at=report.evaluated_at,
        )


class RuleDetailSchema(BaseModel):
    """Rule Explorer detail response."""

    rule_id: str
    category: RuleCategory
    metadata: RuleMetadata
    regulation_reference: str
    threshold: str
    status: str = "active"


class RuleListResponse(BaseModel):
    """Rule Explorer list response."""

    rules: list[RuleDetailSchema]
    total_count: int
    ruleset_version: str
    categories: dict[str, int]


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: str
    version: str
    ruleset_version: str
    rules_count: int
    uptime_seconds: Decimal


class ReadinessResponse(BaseModel):
    """Production-readiness signal for deployment gates."""

    status: str
    production_ready: bool
    checks: dict[str, bool]
    warnings: list[str]


class HumanReviewResponse(BaseModel):
    """Human review workflow response."""

    review_id: UUID
    report_id: UUID
    machine_status: IPOStatus
    status: HumanReviewStatus
    reviewer_name: str | None
    final_decision: HumanFinalDecision | None
    rationale: str | None
    conditions: list[str]
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_domain(cls, review: HumanReviewRecord) -> HumanReviewResponse:
        """Create API schema from a human review record."""
        return cls(
            review_id=review.review_id,
            report_id=review.report_id,
            machine_status=review.machine_status,
            status=review.status,
            reviewer_name=review.reviewer_name,
            final_decision=review.final_decision,
            rationale=review.rationale,
            conditions=review.conditions,
            created_at=review.created_at,
            completed_at=review.completed_at,
        )
