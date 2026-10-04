"""
backend/app/rules/base_rule.py

Abstract base class for every rule.

A rule is a pure function ``CompanyData -> RuleResult``. Legal metadata and
thresholds come from a :class:`RuleSpec` in the versioned ruleset; the rule
class holds only the decision procedure.

Evaluation contract (enforced by helpers here):
  1. Applicability first — a rule whose spec does not cover the declared listing
     route returns NOT_APPLICABLE.
  2. A FAIL is only produced from reliable evidence.
  3. Missing evidence -> INCONCLUSIVE. Present-but-unreliable evidence ->
     REQUIRES_HUMAN_REVIEW. A data gap is never a regulatory breach.

ARCHITECTURAL CONSTRAINTS: may import from models/ and regulatory/ only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, ClassVar, TypeVar

from app.models.company_data import CompanyData, FiscalYear
from app.models.enums import RuleCategory, Verdict
from app.models.evidence import EvidenceRef
from app.models.extracted_value import ExtractedValue
from app.models.rule_result import RuleMetadata, RuleResult
from app.regulatory.registry import RuleSpec, load_ruleset

T = TypeVar("T")

FULL_YEAR_MONTHS = 12


def fmt_crore(value: Decimal) -> str:
    """Format a ₹ crore Decimal, e.g. ``₹3.00 Cr``."""
    return f"₹{value:,.2f} Cr"


def fmt_pct(value: Decimal) -> str:
    """Format a percentage Decimal, e.g. ``25.00%``."""
    return f"{value:.2f}%"


class Inputs:
    """Collects evidence, missing inputs and reliability problems for one evaluation."""

    def __init__(self) -> None:
        self.evidence: list[EvidenceRef] = []
        self.missing: list[str] = []
        self.unreliable: list[str] = []
        self.calculation: list[str] = []

    def get(self, path: str, ev: ExtractedValue[T] | None) -> T | None:
        """Record an input. Returns the value (even if unreliable) or None if missing."""
        if ev is None:
            self.missing.append(path)
            return None
        self.evidence.append(EvidenceRef.from_extracted(path, ev))
        if not ev.is_reliable():
            self.unreliable.append(f"{path}: {ev.review_reason()}")
        return ev.value

    def is_reliable(self, ev: ExtractedValue[Any] | None) -> bool:
        """Whether a recorded input is present and reliable."""
        return ev is not None and ev.is_reliable()

    def require_flag(self, path: str, value: bool | None) -> bool | None:
        """Record a plain (non-extracted) declaration flag."""
        if value is None:
            self.missing.append(path)
        else:
            self.evidence.append(
                EvidenceRef(field_path=path, value=str(value).lower(), kind="manual")
            )
        return value

    def declared(self, path: str, value: str) -> None:
        """Record a declared (non-numeric) case attribute such as the issue type."""
        self.evidence.append(EvidenceRef(field_path=path, value=value, kind="manual"))

    def calc(self, step: str) -> None:
        """Append a calculation step."""
        self.calculation.append(step)

    def calculated(self, path: str, value: str, unit: str | None = None) -> None:
        """Record a calculated value as evidence (kind='calculated')."""
        self.evidence.append(EvidenceRef.calculated(path, value, unit))


class BaseRule(ABC):
    """Abstract base class for all rules."""

    rule_id: ClassVar[str]

    def __init__(self, spec: RuleSpec | None = None) -> None:
        self._spec = spec or load_ruleset().spec(self.rule_id)
        if self._spec.rule_id != self.rule_id:
            raise ValueError(f"Spec {self._spec.rule_id} does not match rule {self.rule_id}.")

    # -- metadata ---------------------------------------------------------

    @property
    def spec(self) -> RuleSpec:
        """The legal metadata and parameters for this rule."""
        return self._spec

    @property
    def category(self) -> RuleCategory:
        """MANDATORY (feeds the case outcome) or ADVISORY."""
        return self._spec.category

    @property
    def metadata(self) -> RuleMetadata:
        """API v0 citation summary derived from the spec."""
        return RuleMetadata(
            regulation=self._spec.instrument,
            section=self._spec.provision,
            clause=None,
            description=self._spec.name,
            category=self._spec.category,
            effective_date=self._spec.effective_from,
            source_url=self._spec.source_url,
        )

    @property
    @abstractmethod
    def required_value(self) -> str:
        """Human-readable statement of the condition."""

    # -- evaluation -------------------------------------------------------

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate the rule. Never raises for missing data."""
        route = company.issue_details.listing_route
        if route not in self._spec.routes:
            return self._result(
                Verdict.NOT_APPLICABLE,
                Inputs(),
                explanation=(
                    f"Not applicable to the declared listing route '{route.value}'. "
                    f"Applicability: {self._spec.applicability}"
                ),
            )
        return self._evaluate(company)

    @abstractmethod
    def _evaluate(self, company: CompanyData) -> RuleResult:
        """Rule-specific decision procedure (route already applicable)."""

    # -- result builders --------------------------------------------------

    def _result(
        self,
        verdict: Verdict,
        inputs: Inputs,
        *,
        explanation: str,
        actual_value: str | None = None,
        gap: str | None = None,
        remediation: list[str] | None = None,
        review_reasons: list[str] | None = None,
    ) -> RuleResult:
        reasons = list(review_reasons or [])
        if verdict == Verdict.REQUIRES_HUMAN_REVIEW:
            reasons = inputs.unreliable + reasons
        return RuleResult(
            rule_id=self.rule_id,
            verdict=verdict,
            category=self._spec.category,
            regulation_reference=f"{self._spec.instrument}, {self._spec.provision}",
            description=self._spec.name,
            required_value=self.required_value,
            actual_value=actual_value,
            gap=gap,
            explanation=explanation,
            evaluated_at=datetime.now(tz=UTC),
            rule_name=self._spec.name,
            rule_version=self._spec.rule_version,
            legal_category=self._spec.legal_category,
            verification_status=self._spec.verification_status,
            source_url=self._spec.source_url,
            applicable=verdict != Verdict.NOT_APPLICABLE,
            calculation=list(inputs.calculation),
            evidence=list(inputs.evidence),
            missing_inputs=list(inputs.missing),
            requires_human_review=bool(reasons) or verdict == Verdict.REQUIRES_HUMAN_REVIEW,
            review_reasons=reasons,
            remediation=list(remediation or []),
            limitations=list(self._spec.limitations),
        )

    def _undetermined(self, inputs: Inputs, actual_value: str | None = None) -> RuleResult:
        """INCONCLUSIVE when inputs are missing, else REQUIRES_HUMAN_REVIEW."""
        if inputs.missing:
            return self._result(
                Verdict.INCONCLUSIVE,
                inputs,
                actual_value=actual_value,
                explanation=(
                    "Cannot determine compliance: required evidence is missing ("
                    + ", ".join(inputs.missing)
                    + "). Missing evidence is not treated as a breach."
                ),
                remediation=[
                    "Provide the missing evidence from the offer document or "
                    "audited / restated financial statements."
                ],
            )
        return self._result(
            Verdict.REQUIRES_HUMAN_REVIEW,
            inputs,
            actual_value=actual_value,
            explanation=(
                "Evidence is present but not reliable enough for an automated "
                "determination; a reviewer must confirm or correct it."
            ),
            remediation=["Confirm or correct the flagged values in the review workspace."],
        )


def preceding_full_years(company: CompanyData, count: int) -> list[FiscalYear]:
    """Return the most recent ``count`` twelve-month periods (oldest first).

    Stub periods (months != 12) are skipped, implementing "preceding three full
    years (of twelve months each)".
    """
    full = [fy for fy in company.financials.fiscal_years if fy.months == FULL_YEAR_MONTHS]
    return full[-count:]
