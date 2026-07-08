"""
backend/app/rules/mandatory/net_worth.py

SEBI ICDR Regulation 26(1)(c) — Net Worth rule.

This module implements one mandatory eligibility rule:

  NetWorthRule (NET_WORTH_1CR):
    The company must have a net worth of at least ₹1 Crore in each of the
    three preceding full fiscal years. Net worth is total equity (paid-up
    capital plus reserves and surplus). Negative net worth in any year
    constitutes an automatic failure.

    If fewer than 3 years of data are available, or if net_worth for any
    of the last 3 years has LOW confidence without human confirmation, the
    rule returns INCONCLUSIVE rather than FAIL.

Regulation: SEBI (ICDR) Regulations, 2018, Regulation 26(1), Clause (c)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.company_data import CompanyData, FiscalYear
from app.models.enums import RuleCategory, Verdict
from app.models.rule_result import RuleMetadata, RuleResult
from app.rules.base_rule import BaseRule

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NET_WORTH_THRESHOLD = Decimal("1")  # ₹1 Crore
_REGULATION = "SEBI (ICDR) Regulations, 2018"
_SECTION = "Regulation 26(1)"
_EFFECTIVE_DATE = date(2018, 11, 1)
_SOURCE_URL = (
    "https://www.sebi.gov.in/legal/regulations/nov-2018/"
    "sebi-icdr-regulations-2018.html"
)


def _fmt_crore(value: Decimal) -> str:
    """Format a Decimal crore value as '₹X.XX Cr'."""
    return f"₹{value:.2f} Cr"


class NetWorthRule(BaseRule):
    """Mandatory rule: Net worth ≥ ₹1 Crore in each of 3 preceding FYs.

    SEBI (ICDR) Regulations, 2018, Regulation 26(1), Clause (c) requires
    that a company seeking a mainboard IPO listing must have a net worth of
    at least ₹1 Crore in each of the three preceding full fiscal years.

    Net worth is the company's total equity: paid-up share capital plus
    reserves and surplus. Negative net worth signals accumulated losses that
    exceed the company's equity base and constitutes an automatic failure.

    Evaluation logic:
      - Requires the last 3 fiscal years from CompanyData.financials.fiscal_years.
      - Returns INCONCLUSIVE if fewer than 3 years are available.
      - Returns INCONCLUSIVE if any year's net_worth ExtractedValue is not
        reliable (confidence=LOW without human confirmation).
      - Returns FAIL if any year has net_worth < ₹1 Crore, with a gap
        message identifying the worst shortfall year and the shortfall amount.
      - Returns PASS only when all 3 years meet or exceed the threshold.

    Example::

        rule = NetWorthRule()
        result = rule.evaluate(company)
        assert result.rule_id == "NET_WORTH_1CR"
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule.

        Returns:
            The string ``"NET_WORTH_1CR"``.
        """
        return "NET_WORTH_1CR"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for the net worth rule.

        Returns:
            RuleMetadata citing SEBI ICDR Reg. 26(1)(c) as the source.
        """
        return RuleMetadata(
            regulation=_REGULATION,
            section=_SECTION,
            clause="Clause (c)",
            description=(
                "Net worth must be at least ₹1 Crore in each of "
                "the three preceding full fiscal years."
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
        return "≥ ₹1 Cr net worth in each of the 3 preceding full fiscal years"

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate net worth compliance across the last 3 fiscal years.

        Checks that net_worth ≥ ₹1 Crore for each of the three most recent
        fiscal years. Returns INCONCLUSIVE if data is missing or unreliable;
        FAIL if any year falls short; PASS otherwise.

        Args:
            company: Canonical company data. Must include at least 3 fiscal
                years with reliable net_worth values.

        Returns:
            A RuleResult with verdict PASS, FAIL, or INCONCLUSIVE.
        """
        fiscal_years = company.financials.fiscal_years

        if len(fiscal_years) < 3:
            return self._build_inconclusive(
                reason=(
                    f"only {len(fiscal_years)} fiscal year(s) available; "
                    "3 preceding full fiscal years are required"
                ),
                actual_value=(
                    f"{len(fiscal_years)} FY(s) available"
                    if fiscal_years
                    else "no fiscal year data"
                ),
            )

        # Take the most recent 3 fiscal years (list is oldest-first)
        last_three: list[FiscalYear] = list(fiscal_years[-3:])

        # Reliability check before any value comparisons
        for fy in last_three:
            if not fy.net_worth.is_reliable():
                return self._build_inconclusive(
                    reason=(
                        f"net worth for {fy.year_label} has "
                        "low confidence without human confirmation"
                    ),
                    actual_value=f"unreliable data in {fy.year_label}",
                )

        # Evaluate each year against the ₹1 Crore threshold
        failing_years: list[tuple[str, Decimal]] = []
        year_summaries: list[str] = []

        for fy in last_three:
            nw: Decimal = fy.net_worth.value
            year_summaries.append(f"{fy.year_label}: {_fmt_crore(nw)}")
            if nw < _NET_WORTH_THRESHOLD:
                failing_years.append((fy.year_label, nw))

        actual_value = "; ".join(year_summaries)

        if not failing_years:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                explanation=(
                    "Net worth met the ₹1 Crore threshold in all "
                    f"three preceding fiscal years: {actual_value}."
                ),
            )

        # Identify the worst shortfall year for the gap message
        worst_label, worst_nw = min(failing_years, key=lambda t: t[1])
        shortfall: Decimal = _NET_WORTH_THRESHOLD - worst_nw
        gap = (
            f"{_fmt_crore(shortfall)} below ₹1 Cr threshold in {worst_label}"
        )

        failed_labels = ", ".join(label for label, _ in failing_years)
        explanation = (
            f"Net worth fell below the ₹1 Crore threshold in "
            f"{len(failing_years)} of 3 fiscal year(s): {failed_labels}. "
            f"Actual values — {actual_value}. "
            f"Worst shortfall: {_fmt_crore(worst_nw)} in {worst_label} "
            f"({_fmt_crore(shortfall)} below the ₹1 Cr minimum)."
        )

        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=explanation,
        )
