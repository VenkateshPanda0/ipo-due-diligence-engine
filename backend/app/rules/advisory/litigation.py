"""
backend/app/rules/advisory/litigation.py

Advisory rule: Litigation risk assessment (LITIGATION_RISK).

SEBI ICDR Schedule VI requires disclosure of material pending litigation
with quantified financial exposure. Criminal cases against the company
or its promoters are a significant red flag that investment bankers
and SEBI reviewers closely scrutinize.

Import constraints:
  - MUST NOT import from: app.parser, app.api, app.services, app.engine
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import RuleCategory, Verdict
from app.models.rule_result import RuleMetadata, RuleResult
from app.rules.base_rule import BaseRule

_EFFECTIVE_DATE_ICDR = date(2018, 11, 1)
_SEBI_ICDR_URL = (
    "https://www.sebi.gov.in/legal/regulations/nov-2018/sebi-icdr-2018.html"
)

# Materiality threshold: litigation exposure > 20% of latest year's net worth
_MATERIALITY_NET_WORTH_RATIO = Decimal("0.20")


class LitigationRiskRule(BaseRule):
    """Advisory rule: material pending litigation must be disclosed and quantified.

    SEBI ICDR Schedule VI requires that the DRHP discloses all pending
    legal proceedings involving the company, promoters, directors, or
    group companies. The rule flags:
      1. Criminal cases — a high-severity risk requiring human review.
      2. Material exposure — litigation with total exposure > 20% of
         latest year's net worth, flagged as significant financial risk.

    Rule ID: LITIGATION_RISK
    """

    @property
    def rule_id(self) -> str:
        """Return the unique identifier for this rule."""
        return "LITIGATION_RISK"

    @property
    def metadata(self) -> RuleMetadata:
        """Return regulatory metadata for this rule."""
        return RuleMetadata(
            regulation="SEBI (ICDR) Regulations, 2018",
            section="Schedule VI",
            clause=None,
            description=(
                "Material pending litigation must be disclosed with quantified "
                "exposure; criminal cases are flagged as high-severity risk"
            ),
            category=RuleCategory.ADVISORY,
            effective_date=_EFFECTIVE_DATE_ICDR,
            source_url=_SEBI_ICDR_URL,
        )

    @property
    def _required_value(self) -> str:
        return (
            "No criminal cases; total litigation exposure \u2264 20% of net worth; "
            "all pending cases disclosed with quantified exposure"
        )

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate litigation risk and disclosure adequacy.

        Args:
            company: The canonical company schema.

        Returns:
            INCONCLUSIVE if litigation data is unreliable.
            FAIL if criminal cases exist or exposure is material.
            PASS if no material litigation risk is identified.
        """
        lit = company.litigation

        # Reliability checks
        if not lit.has_criminal_cases.is_reliable():
            return self._build_inconclusive(
                "has_criminal_cases has LOW confidence and has not been human-confirmed"
            )
        if not lit.total_exposure.is_reliable():
            return self._build_inconclusive(
                "total_exposure has LOW confidence and has not been human-confirmed"
            )

        has_criminal = lit.has_criminal_cases.value
        total_exposure = lit.total_exposure.value
        n_cases = len(lit.pending_cases)

        failures: list[str] = []

        # Check 1: Criminal cases (automatic FAIL)
        if has_criminal:
            failures.append(
                "Criminal case(s) are pending against the company or its promoters/directors"
            )

        # Check 2: Material exposure relative to net worth
        if company.financials.fiscal_years:
            latest_year = company.financials.fiscal_years[-1]
            if latest_year.net_worth.is_reliable():
                net_worth = latest_year.net_worth.value
                if net_worth > Decimal("0") and total_exposure > Decimal("0"):
                    exposure_ratio = total_exposure / net_worth
                    if exposure_ratio > _MATERIALITY_NET_WORTH_RATIO:
                        failures.append(
                            f"Total litigation exposure (\u20b9{total_exposure:.2f} Cr) is "
                            f"{exposure_ratio * 100:.1f}% of net worth "
                            f"(\u20b9{net_worth:.2f} Cr), exceeding the 20% materiality threshold"
                        )

        actual_value = (
            f"{n_cases} pending case(s), total exposure: \u20b9{total_exposure:.2f} Cr, "
            f"criminal cases: {'Yes' if has_criminal else 'No'}"
        )

        if failures:
            gap = "; ".join(failures)
            return self._build_result(
                verdict=Verdict.FAIL,
                actual_value=actual_value,
                gap=gap,
                explanation=(
                    f"Litigation risk assessment flagged material concerns: {gap}. "
                    "These must be disclosed in the DRHP and reviewed by SEBI."
                ),
            )

        if n_cases == 0:
            explanation = "No pending litigation cases. Clean litigation history."
        else:
            explanation = (
                f"{n_cases} pending case(s) with total exposure of "
                f"\u20b9{total_exposure:.2f} Cr. No criminal cases. "
                "Exposure is within the 20% net worth materiality threshold. "
                "All cases appear to be disclosed and quantified."
            )

        return self._build_result(
            verdict=Verdict.PASS,
            actual_value=actual_value,
            explanation=explanation,
        )
