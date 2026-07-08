"""
backend/app/models/ipo_report.py

IPOReport aggregate and supporting models.

EligibilityProgress tracks pass/fail/inconclusive counts for a set of
RuleResults. GapAnalysisItem quantifies the gap for a failed mandatory
rule and projects earliest eligibility. IPOReport is the top-level
aggregate returned by the Decision Engine.

This module MUST NOT import from:
  - app.rules, app.parser, app.api, app.engine, app.services

All models are frozen (immutable) after construction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import IPOStatus
from app.models.rule_result import RuleResult
from app.models.ruleset_version import RulesetVersion


class EligibilityProgress(BaseModel):
    """Counts of pass/fail/inconclusive verdicts for a set of rules.

    Used to communicate progress (e.g., "18 of 22 requirements satisfied")
    without using a blended score. One instance is produced for mandatory
    rules and one for advisory rules.

    Attributes:
        total_rules: Total number of rules evaluated.
        passed: Number of rules that returned PASS.
        failed: Number of rules that returned FAIL.
        inconclusive: Number of rules that returned INCONCLUSIVE.
        pass_percentage: Percentage of rules that passed (0–100).
        failed_rule_ids: IDs of all rules that returned FAIL.

    Example:
        >>> progress = EligibilityProgress(
        ...     total_rules=11,
        ...     passed=9,
        ...     failed=2,
        ...     inconclusive=0,
        ...     pass_percentage=Decimal("81.82"),
        ...     failed_rule_ids=["NTA_3CR", "NET_WORTH_1CR"],
        ... )
        >>> progress.passed
        9
    """

    model_config = ConfigDict(frozen=True)

    total_rules: int
    passed: int
    failed: int
    inconclusive: int
    pass_percentage: Decimal
    failed_rule_ids: list[str]

    @model_validator(mode="after")
    def validate_counts(self) -> EligibilityProgress:
        """Ensure passed + failed + inconclusive == total_rules.

        Returns:
            The validated instance.

        Raises:
            ValueError: If the counts do not sum to total_rules.
        """
        total = self.passed + self.failed + self.inconclusive
        if total != self.total_rules:
            raise ValueError(
                f"passed ({self.passed}) + failed ({self.failed}) + "
                f"inconclusive ({self.inconclusive}) = {total} "
                f"does not equal total_rules ({self.total_rules})."
            )
        return self


class GapAnalysisItem(BaseModel):
    """Quantified gap and remediation plan for a failed mandatory rule.

    Produced by the Gap Planner for every failed mandatory rule. Provides
    the company with actionable information: how large is the shortfall,
    when could they realistically become eligible, and what steps would
    close the gap.

    Attributes:
        rule_id: ID of the failed rule this gap analysis covers.
        gap_size: Human-readable description of the shortfall,
            e.g., "₹3.2 Cr below the ₹15 Cr threshold".
        earliest_eligible_fy: Projected earliest fiscal year when the
            company could become eligible, e.g., "FY2028".
            "Undetermined" if trend data is insufficient for projection.
        remediation_steps: Specific, actionable steps to close the gap.
            Must be non-empty.
        current_value: Human-readable current value, e.g., "₹11.8 Cr".
        required_value: Human-readable required value, e.g., "≥ ₹15 Cr".

    Example:
        >>> item = GapAnalysisItem(
        ...     rule_id="AVG_OPERATING_PROFIT_15CR",
        ...     gap_size="₹3.2 Cr below the ₹15 Cr threshold",
        ...     earliest_eligible_fy="FY2028",
        ...     remediation_steps=[
        ...         "Improve operating margins through cost reduction",
        ...         "Grow revenue to ₹75+ Cr to support profit targets",
        ...     ],
        ...     current_value="₹11.8 Cr",
        ...     required_value="≥ ₹15 Cr average across 3 of 5 FYs",
        ... )
        >>> item.rule_id
        'AVG_OPERATING_PROFIT_15CR'
    """

    model_config = ConfigDict(frozen=True)

    rule_id: str
    gap_size: str
    earliest_eligible_fy: str
    remediation_steps: list[str]
    current_value: str
    required_value: str

    @model_validator(mode="after")
    def validate_remediation_steps(self) -> GapAnalysisItem:
        """Ensure at least one remediation step is provided.

        Returns:
            The validated instance.

        Raises:
            ValueError: If remediation_steps is empty.
        """
        if not self.remediation_steps:
            raise ValueError(
                f"GapAnalysisItem for rule '{self.rule_id}' must have at least "
                "one remediation step."
            )
        return self


class IPOReport(BaseModel):
    """Top-level aggregate produced by the Decision Engine.

    IPOReport is the final output of the entire deterministic pipeline.
    It encodes the eligibility verdict, all individual rule results
    (mandatory and advisory), gap analysis for failed rules, and
    free-form observations from pattern matching.

    Given the same CompanyData and RulesetVersion, the pipeline always
    produces an IPOReport with an identical status, rule results, and
    gap analysis. The report_id and evaluated_at timestamp will differ
    (these are generation metadata, not deterministic outputs).

    Attributes:
        report_id: Unique identifier for this report generation event.
        company_name: Name of the company being evaluated.
        status: Overall IPO eligibility status (ELIGIBLE, NOT_ELIGIBLE,
            or NEEDS_REVIEW).
        mandatory_progress: Pass/fail counts for the 11 mandatory rules.
        advisory_progress: Pass/fail counts for the 5 advisory rules.
        mandatory_results: Ordered list of RuleResult for all mandatory rules.
        advisory_results: Ordered list of RuleResult for all advisory rules.
        gap_analysis: GapAnalysisItem for every failed mandatory rule.
        observations: Free-form observations from pattern matching
            (e.g., declining revenue trend, very young company).
        ruleset_version: The ruleset version this report was evaluated against.
        evaluated_at: UTC timestamp when this report was generated.

    Example:
        >>> # Use DecisionEngine.assemble_report() to construct this.
        >>> # Direct construction is for testing only.
    """

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
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC)
    )
