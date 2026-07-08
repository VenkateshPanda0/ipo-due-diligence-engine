"""
backend/app/rules/advisory/rpt.py

Advisory rule: Related Party Transaction disclosure (RPT_DISCLOSURE).

SEBI LODR Regulation 23 requires that all related party transactions are
disclosed and certified as being conducted at arm's length. High RPT volumes
relative to revenue are flagged as a governance risk.

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

_EFFECTIVE_DATE_LODR = date(2015, 9, 2)
_SEBI_LODR_URL = (
    "https://www.sebi.gov.in/legal/regulations/sep-2015/sebi-lodr-regulations-2015.html"
)

# Threshold above which high RPT volume triggers an advisory warning even if certified
_HIGH_RPT_REVENUE_RATIO_THRESHOLD = Decimal("0.20")  # 20% of latest year revenue


class RPTDisclosureRule(BaseRule):
    """Advisory rule: all related party transactions must be arm's-length certified.

    SEBI LODR Regulation 23 mandates that:
      1. All RPTs are disclosed to shareholders.
      2. All RPTs are conducted at arm's length, certified by the audit committee.

    Additionally, a high ratio of RPT volume to revenue (> 20% of latest year's
    revenue) is flagged as a governance risk warning, even when arm's length
    certification is present.

    Rule ID: RPT_DISCLOSURE
    """

    @property
    def rule_id(self) -> str:
        """Return the unique identifier for this rule."""
        return "RPT_DISCLOSURE"

    @property
    def metadata(self) -> RuleMetadata:
        """Return regulatory metadata for this rule."""
        return RuleMetadata(
            regulation="SEBI (LODR) Regulations, 2015",
            section="Regulation 23",
            clause=None,
            description=(
                "All related party transactions must be disclosed and certified "
                "as arm's length by the audit committee"
            ),
            category=RuleCategory.ADVISORY,
            effective_date=_EFFECTIVE_DATE_LODR,
            source_url=_SEBI_LODR_URL,
        )

    @property
    def _required_value(self) -> str:
        return (
            "All related party transactions disclosed and certified at arm's length; "
            "RPT volume should not exceed 20% of latest year revenue"
        )

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate RPT disclosure and arm's length certification.

        Args:
            company: The canonical company schema.

        Returns:
            INCONCLUSIVE if RPT data is missing or unreliable.
            FAIL if arm's length not certified.
            PASS (with possible high-volume warning) otherwise.
        """
        rpt = company.rpt

        # If no transactions, check arm_length_certified reliability
        if not rpt.arm_length_certified.is_reliable():
            return self._build_inconclusive(
                "arm_length_certified has LOW confidence and has not been human-confirmed"
            )

        if not rpt.total_rpt_value.is_reliable():
            return self._build_inconclusive(
                "total_rpt_value has LOW confidence and has not been human-confirmed"
            )

        arm_length = rpt.arm_length_certified.value
        total_rpt = rpt.total_rpt_value.value
        n_transactions = len(rpt.transactions)

        actual_value = (
            f"\u20b9{total_rpt:.2f} Cr total RPT value across {n_transactions} transaction(s), "
            f"arm's length certified: {arm_length}"
        )

        if not arm_length:
            return self._build_result(
                verdict=Verdict.FAIL,
                actual_value=actual_value,
                gap="Related party transactions have NOT been certified as arm's length",
                explanation=(
                    "LODR Reg. 23 requires all related party transactions to be certified "
                    "at arm's length by the audit committee. This certification is absent. "
                    "Disclosure and arm's length certification must be obtained before IPO."
                ),
            )

        # Check for high RPT volume as advisory warning
        high_volume_warning = ""
        if company.financials.fiscal_years and total_rpt > Decimal("0"):
            latest_year = company.financials.fiscal_years[-1]
            if latest_year.revenue.is_reliable():
                latest_revenue = latest_year.revenue.value
                if latest_revenue > Decimal("0"):
                    ratio = total_rpt / latest_revenue
                    if ratio > _HIGH_RPT_REVENUE_RATIO_THRESHOLD:
                        high_volume_warning = (
                            f" Warning: RPT volume (\u20b9{total_rpt:.2f} Cr) represents "
                            f"{ratio * 100:.1f}% of latest year revenue "
                            f"(\u20b9{latest_revenue:.2f} Cr), exceeding the 20% advisory "
                            "threshold."
                        )

        return self._build_result(
            verdict=Verdict.PASS,
            actual_value=actual_value,
            explanation=(
                f"All related party transactions (\u20b9{total_rpt:.2f} Cr across "
                f"{n_transactions} transaction(s)) are certified at arm's length per "
                f"LODR Reg. 23." + high_volume_warning
            ),
        )
