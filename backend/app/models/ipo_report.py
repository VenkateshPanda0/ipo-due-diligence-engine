"""
backend/app/models/ipo_report.py

IPOReport aggregate and supporting models.

Fields added for ruleset 2.0.0 have defaults so that reports persisted under
ruleset 1.0.0 still deserialise. A stored report is an immutable snapshot of
what was evaluated: historical reports are never re-evaluated in place.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import IPOStatus, ListingRoute, ScreeningOutcome
from app.models.rule_result import RuleResult
from app.models.ruleset_version import RulesetVersion

ENGINE_VERSION = "2.0.1"

STANDARD_LIMITATIONS: tuple[str, ...] = (
    "This is a decision-support screening against an explicitly limited set of rules; it is "
    "not a legal opinion and not a determination of IPO eligibility or approval.",
    "The ruleset has not been reviewed by a qualified securities-law professional "
    "(REGULATORY_VALIDATION_CONFIRMED is false unless stated otherwise).",
    "Extracted facts can contain errors; values flagged for review must be verified against "
    "the source documents.",
    "A 'no failure identified' outcome means no supported mandatory check failed on the "
    "evidence provided. Unsupported provisions are not evaluated.",
)


class EligibilityProgress(BaseModel):
    """Verdict counts for a group of rules."""

    model_config = ConfigDict(frozen=True)

    total_rules: int
    passed: int
    failed: int
    inconclusive: int
    pass_percentage: Decimal
    failed_rule_ids: list[str]
    requires_review: int = 0
    not_applicable: int = 0

    @model_validator(mode="after")
    def validate_counts(self) -> EligibilityProgress:
        total = (
            self.passed
            + self.failed
            + self.inconclusive
            + self.requires_review
            + self.not_applicable
        )
        if total != self.total_rules:
            raise ValueError(
                f"verdict counts sum to {total}, which does not equal total_rules "
                f"({self.total_rules})."
            )
        return self


class GapAnalysisItem(BaseModel):
    """Remediation planning entry for a failed or undetermined mandatory rule."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    gap_size: str
    earliest_eligible_fy: str
    remediation_steps: list[str]
    current_value: str
    required_value: str
    verdict: str | None = None
    professional_review_required: bool = True

    @model_validator(mode="after")
    def validate_remediation_steps(self) -> GapAnalysisItem:
        if not self.remediation_steps:
            raise ValueError(
                f"GapAnalysisItem for rule '{self.rule_id}' must have at least one remediation "
                "step."
            )
        return self


class IPOReport(BaseModel):
    """Complete, immutable screening report."""

    model_config = ConfigDict(frozen=True)

    report_id: UUID = Field(default_factory=uuid4)
    company_name: str
    status: IPOStatus
    mandatory_progress: EligibilityProgress
    advisory_progress: EligibilityProgress
    mandatory_results: list[RuleResult]
    advisory_results: list[RuleResult]
    gap_analysis: list[GapAnalysisItem]
    observations: list[str]
    ruleset_version: RulesetVersion
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    outcome: ScreeningOutcome | None = None
    listing_route: ListingRoute | None = None
    engine_version: str | None = None
    case_id: UUID | None = None
    input_sha256: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    extraction_run_ids: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    regulatory_validation_confirmed: bool = False
