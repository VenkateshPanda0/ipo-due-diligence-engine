"""
backend/app/models/rule_result.py

Rule metadata and per-rule evaluation results.

New fields added for ruleset 2.0.0 all have defaults so that reports stored by
ruleset 1.0.0 still deserialise unchanged.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LegalCategory, RuleCategory, Verdict, VerificationStatus
from app.models.evidence import EvidenceRef
from app.models.source_citation import SourceCitation


class RuleMetadata(BaseModel):
    """Regulatory citation summary for a rule (API v0 shape)."""

    model_config = ConfigDict(frozen=True)

    regulation: str
    section: str
    clause: str | None = None
    description: str
    category: RuleCategory
    effective_date: date | None = None
    source_url: str | None = None


class RuleResult(BaseModel):
    """Outcome of evaluating one rule against one CompanyData snapshot.

    Attributes beyond v1:
        rule_name / rule_version / legal_category / verification_status: copied
            from the rule spec so a stored result is self-describing.
        applicable: False when the verdict is NOT_APPLICABLE.
        calculation: Ordered human-readable calculation steps.
        evidence: Every input fact (and calculated value) used.
        missing_inputs: Field paths whose absence prevented a determination.
        requires_human_review / review_reasons: Evidence-quality or
            interpretive issues a reviewer must resolve.
        remediation: Rule-specific guidance (never a guarantee of eligibility).
        limitations: Known limits of the rule implementation.
    """

    model_config = ConfigDict(frozen=True)

    rule_id: str
    verdict: Verdict
    category: RuleCategory
    regulation_reference: str
    description: str
    required_value: str
    actual_value: str | None = None
    gap: str | None = None
    source_citation: SourceCitation | None = None
    explanation: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    rule_name: str = ""
    rule_version: str | None = None
    legal_category: LegalCategory | None = None
    verification_status: VerificationStatus | None = None
    source_url: str | None = None
    applicable: bool = True
    calculation: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    remediation: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
