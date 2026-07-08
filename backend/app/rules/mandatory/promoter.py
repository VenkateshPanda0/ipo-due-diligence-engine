"""
backend/app/rules/mandatory/promoter.py

Promoter mandatory rules: PROMOTER_CONTRIBUTION_20 and PROMOTER_LOCK_IN.

This module implements two related mandatory eligibility rules:

  1. PromoterContributionRule (PROMOTER_CONTRIBUTION_20):
     Promoter(s) must contribute at least 20% of the post-issue paid-up
     capital. This is evaluated using the post_issue_holding ExtractedValue
     in PromoterData, which represents the promoter group's aggregate
     percentage of total post-issue capital.

  2. PromoterLockInRule (PROMOTER_LOCK_IN):
     The promoter contribution must be locked in for a minimum period:
       - Standard issues: 18 months from the date of allotment.
       - Capex issues (where proceeds are for capital expenditure):
         36 months (3 years) from the date of allotment.
     The is_capex_issue flag in PromoterData determines which threshold applies.

Regulations:
  - PROMOTER_CONTRIBUTION_20: SEBI (ICDR) Regulations, 2018, Regulation 32
  - PROMOTER_LOCK_IN: SEBI (ICDR) Regulations, 2018, Regulation 36
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import RuleCategory, Verdict
from app.models.rule_result import RuleMetadata, RuleResult
from app.rules.base_rule import BaseRule

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_REGULATION = "SEBI (ICDR) Regulations, 2018"
_EFFECTIVE_DATE = date(2018, 11, 1)
_SOURCE_URL = (
    "https://www.sebi.gov.in/legal/regulations/nov-2018/"
    "sebi-icdr-regulations-2018.html"
)

# PromoterContributionRule constants
_MIN_CONTRIBUTION_PCT = Decimal("20")  # 20% of post-issue capital

# PromoterLockInRule constants
_LOCK_IN_STANDARD_MONTHS = 18   # 18 months for standard issues
_LOCK_IN_CAPEX_MONTHS = 36      # 36 months (3 years) for capex issues


def _fmt_pct(value: Decimal) -> str:
    """Format a Decimal percentage as 'X.XX%'."""
    return f"{value:.2f}%"


class PromoterContributionRule(BaseRule):
    """Mandatory rule: Promoter contribution ≥ 20% of post-issue capital.

    SEBI (ICDR) Regulations, 2018, Regulation 32 requires that promoter(s)
    contribute at least 20% of the post-issue paid-up capital. This ensures
    that the promoter group retains meaningful skin in the game after the IPO.

    The check uses PromoterData.post_issue_holding, which is the aggregate
    promoter shareholding as a percentage of total post-issue capital
    (i.e., after the IPO allotment).

    Evaluation logic:
      - Returns INCONCLUSIVE if post_issue_holding is not reliable.
      - Returns PASS if post_issue_holding ≥ 20%.
      - Returns FAIL otherwise, with a gap message showing the shortfall.

    Example::

        rule = PromoterContributionRule()
        result = rule.evaluate(company)
        assert result.rule_id == "PROMOTER_CONTRIBUTION_20"
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule.

        Returns:
            The string ``"PROMOTER_CONTRIBUTION_20"``.
        """
        return "PROMOTER_CONTRIBUTION_20"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for the promoter contribution rule.

        Returns:
            RuleMetadata citing SEBI ICDR Reg. 32.
        """
        return RuleMetadata(
            regulation=_REGULATION,
            section="Regulation 32",
            clause=None,
            description=(
                "Promoter(s) must contribute at least 20% of post-issue "
                "paid-up capital."
            ),
            category=RuleCategory.MANDATORY,
            effective_date=_EFFECTIVE_DATE,
            source_url=_SOURCE_URL,
        )

    @property
    def _required_value(self) -> str:
        """Human-readable threshold description.

        Returns:
            A string describing the regulatory requirement.
        """
        return "≥ 20% of post-issue paid-up capital"

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate promoter contribution against the 20% post-issue threshold.

        Checks that post_issue_holding ≥ 20%. Returns INCONCLUSIVE if data
        is unreliable; FAIL if the contribution falls short; PASS otherwise.

        Args:
            company: Canonical company data with promoter shareholding details.

        Returns:
            A RuleResult with verdict PASS, FAIL, or INCONCLUSIVE.
        """
        post_issue_ev = company.promoter.post_issue_holding

        if not post_issue_ev.is_reliable():
            return self._build_inconclusive(
                reason=(
                    "promoter post_issue_holding has low confidence without "
                    "human confirmation"
                ),
                actual_value=None,
            )

        post_issue_pct: Decimal = post_issue_ev.value
        actual_value = f"Promoter holds {_fmt_pct(post_issue_pct)} post-issue"

        if post_issue_pct >= _MIN_CONTRIBUTION_PCT:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                explanation=(
                    f"Promoter post-issue holding of {_fmt_pct(post_issue_pct)} "
                    f"meets the minimum {_fmt_pct(_MIN_CONTRIBUTION_PCT)} "
                    "required by SEBI (ICDR) Regulations, 2018, Regulation 32."
                ),
            )

        shortfall: Decimal = _MIN_CONTRIBUTION_PCT - post_issue_pct
        gap = (
            f"Promoter holds {_fmt_pct(post_issue_pct)} post-issue; "
            f"minimum required is {_fmt_pct(_MIN_CONTRIBUTION_PCT)} "
            f"(shortfall: {_fmt_pct(shortfall)})"
        )
        explanation = (
            f"Promoter post-issue holding of {_fmt_pct(post_issue_pct)} "
            f"is below the minimum {_fmt_pct(_MIN_CONTRIBUTION_PCT)} "
            "required by SEBI (ICDR) Regulations, 2018, Regulation 32. "
            f"Shortfall: {_fmt_pct(shortfall)}."
        )

        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=explanation,
        )


class PromoterLockInRule(BaseRule):
    """Mandatory rule: Promoter shares must be locked in for the required period.

    SEBI (ICDR) Regulations, 2018, Regulation 36 mandates a minimum lock-in
    period for the promoter contribution:

      - Standard issues:  18 months from the date of allotment.
      - Capex issues:     36 months (3 years) from the date of allotment.

    The is_capex_issue flag in PromoterData switches between the two thresholds.
    The check reads lock_in_months from PromoterData to determine the committed
    lock-in period.

    Evaluation logic:
      - Returns INCONCLUSIVE if lock_in_months is not reliable.
      - Selects the applicable threshold based on is_capex_issue.
      - Returns PASS if lock_in_months ≥ required minimum.
      - Returns FAIL otherwise, with a gap message.

    Example::

        rule = PromoterLockInRule()
        result = rule.evaluate(company)
        assert result.rule_id == "PROMOTER_LOCK_IN"
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule.

        Returns:
            The string ``"PROMOTER_LOCK_IN"``.
        """
        return "PROMOTER_LOCK_IN"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for the promoter lock-in rule.

        Returns:
            RuleMetadata citing SEBI ICDR Reg. 36.
        """
        return RuleMetadata(
            regulation=_REGULATION,
            section="Regulation 36",
            clause=None,
            description=(
                "Promoter contribution must be locked in for ≥ 18 months "
                "(standard issues) or ≥ 36 months (capex issues)."
            ),
            category=RuleCategory.MANDATORY,
            effective_date=_EFFECTIVE_DATE,
            source_url=_SOURCE_URL,
        )

    @property
    def _required_value(self) -> str:
        """Human-readable threshold description.

        Returns:
            A string describing the dual-threshold lock-in requirement.
        """
        return (
            "≥ 18 months lock-in (standard issues); "
            "≥ 36 months lock-in (capex issues)"
        )

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate the promoter lock-in period against the applicable minimum.

        Reads is_capex_issue to determine the applicable threshold, then
        checks that lock_in_months meets or exceeds that threshold.

        Args:
            company: Canonical company data with promoter lock-in details.

        Returns:
            A RuleResult with verdict PASS, FAIL, or INCONCLUSIVE.
        """
        lock_in_ev = company.promoter.lock_in_months
        is_capex = company.promoter.is_capex_issue

        if not lock_in_ev.is_reliable():
            return self._build_inconclusive(
                reason=(
                    "lock_in_months has low confidence without "
                    "human confirmation"
                ),
                actual_value=None,
            )

        lock_in_months: int = lock_in_ev.value
        required_months: int = (
            _LOCK_IN_CAPEX_MONTHS if is_capex else _LOCK_IN_STANDARD_MONTHS
        )
        issue_type_label = "capex issue" if is_capex else "standard issue"
        actual_value = (
            f"{lock_in_months} months lock-in "
            f"(issue type: {issue_type_label})"
        )

        if lock_in_months >= required_months:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                explanation=(
                    f"Promoter lock-in period of {lock_in_months} months "
                    f"meets the {required_months}-month minimum required for "
                    f"a {issue_type_label} under SEBI (ICDR) Regulations, "
                    "2018, Regulation 36."
                ),
            )

        shortfall: int = required_months - lock_in_months
        gap = (
            f"Lock-in is {lock_in_months} months; "
            f"minimum required for a {issue_type_label} is {required_months} months "
            f"(shortfall: {shortfall} month{'s' if shortfall != 1 else ''})"
        )
        explanation = (
            f"Promoter lock-in period of {lock_in_months} months is below "
            f"the {required_months}-month minimum required for a {issue_type_label} "
            "under SEBI (ICDR) Regulations, 2018, Regulation 36. "
            f"Shortfall: {shortfall} month{'s' if shortfall != 1 else ''}."
        )

        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=explanation,
        )
