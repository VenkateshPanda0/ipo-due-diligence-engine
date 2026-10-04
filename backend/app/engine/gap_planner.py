"""
backend/app/engine/gap_planner.py

Builds remediation-planning items for mandatory rules that FAIL or cannot be
determined.

Guidance is never presented as a guarantee: every item is marked as requiring
professional review, and the "earliest eligible" field is only populated where
the rule is period-based and a projection is meaningful.

ARCHITECTURAL CONSTRAINTS: may import from models/ only.
"""

from __future__ import annotations

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.ipo_report import GapAnalysisItem
from app.models.rule_result import RuleResult

_PERIOD_BASED = frozenset(
    {"NTA_3CR", "MONETARY_ASSETS_50PCT", "AVG_OPERATING_PROFIT_15CR", "NET_WORTH_1CR"}
)
_UNDETERMINED = frozenset({Verdict.INCONCLUSIVE, Verdict.REQUIRES_HUMAN_REVIEW})


def _latest_label(company: CompanyData) -> str | None:
    fys = company.financials.fiscal_years
    return fys[-1].year_label if fys else None


class GapPlanner:
    """Generate GapAnalysisItem entries for actionable mandatory results."""

    def generate(
        self, mandatory_results: list[RuleResult], company: CompanyData
    ) -> list[GapAnalysisItem]:
        """Return one item per mandatory FAIL / INCONCLUSIVE / REQUIRES_HUMAN_REVIEW result."""
        items: list[GapAnalysisItem] = []
        for result in mandatory_results:
            if result.verdict == Verdict.FAIL:
                items.append(self._failure_item(result, company))
            elif result.verdict in _UNDETERMINED:
                items.append(self._evidence_item(result))
        return items

    @staticmethod
    def _failure_item(result: RuleResult, company: CompanyData) -> GapAnalysisItem:
        latest = _latest_label(company)
        if result.rule_id in _PERIOD_BASED and latest is not None:
            earliest = (
                f"Not before the next full financial year after {latest} — re-test once restated "
                "results are available (projection only)"
            )
        else:
            earliest = "Not period-based — depends on the remediation taken"
        steps = list(result.remediation) or ["Obtain professional advice on remediation options."]
        steps.append(
            "Remediation suggestions are not a guarantee of eligibility; confirm with securities "
            "counsel and the lead managers."
        )
        return GapAnalysisItem(
            rule_id=result.rule_id,
            gap_size=result.gap or "Requirement not met",
            earliest_eligible_fy=earliest,
            remediation_steps=steps,
            current_value=result.actual_value or "N/A",
            required_value=result.required_value,
            verdict=result.verdict.value,
        )

    @staticmethod
    def _evidence_item(result: RuleResult) -> GapAnalysisItem:
        steps = list(result.remediation)
        if result.missing_inputs:
            steps.append("Missing evidence: " + ", ".join(result.missing_inputs))
        if result.review_reasons:
            steps.append("Review required: " + "; ".join(result.review_reasons))
        if not steps:
            steps = ["Provide or confirm the evidence needed to evaluate this rule."]
        return GapAnalysisItem(
            rule_id=result.rule_id,
            gap_size="Not determinable on current evidence",
            earliest_eligible_fy="Not applicable — evidence gap, not a regulatory failure",
            remediation_steps=steps,
            current_value=result.actual_value or "N/A",
            required_value=result.required_value,
            verdict=result.verdict.value,
        )
