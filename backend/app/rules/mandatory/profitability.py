"""
backend/app/rules/mandatory/profitability.py

SEBI ICDR Regulation 26(1)(b) — Average Operating Profit rule.

This module implements the mandatory profitability eligibility rule:

  ProfitabilityRule (AVG_OPERATING_PROFIT_15CR):
    The company must have an average pre-tax operating profit of at least
    ₹15 Crore, computed over the BEST 3 of the preceding 5 fiscal years.

The "best 3 of 5" formulation is deliberate: SEBI recognises that companies
may have one or two weaker years and does not penalise them provided their
overall profitability track record over the window is strong. The rule
selects the three highest-profit years within the preceding five years and
averages only those.

If fewer than 3 years of financial data are available, the rule returns
INCONCLUSIVE rather than FAIL, because inability to verify data is not
the same as failing the regulation.

Regulation: SEBI (ICDR) Regulations, 2018, Regulation 26(1), Clause (b)
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

_PROFIT_THRESHOLD = Decimal("15")    # ₹15 Crore
_BEST_OF = 3                         # select best 3 years
_WINDOW = 5                          # from the preceding 5 years
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


class ProfitabilityRule(BaseRule):
    """Mandatory rule: Average operating profit ≥ ₹15 Crore (best 3 of 5 FYs).

    SEBI (ICDR) Regulations, 2018, Regulation 26(1), Clause (b) requires that
    a company has an average pre-tax operating profit of at least ₹15 Crore
    computed across at least 3 of the 5 preceding fiscal years, selecting the
    3 best (highest-profit) years.

    Evaluation logic:
      - Takes the last 5 fiscal years from CompanyData.financials.fiscal_years
        (or all years available if fewer than 5).
      - Returns INCONCLUSIVE if fewer than 3 years are available (cannot
        compute a 3-year average with only 1 or 2 data points).
      - Sorts the available years by operating_profit descending and picks
        the top 3 (the "best" years).
      - Returns INCONCLUSIVE if any of the selected best-3 years has an
        operating_profit ExtractedValue that is not reliable.
      - Computes the average of the selected 3 years using Decimal arithmetic.
      - Returns PASS if average ≥ ₹15 Crore, FAIL otherwise.

    Note on reliability check ordering:
      Reliability is checked AFTER selecting the best 3 years. This is
      correct because a low-confidence year outside the best 3 should not
      block evaluation — the rule only consumes values from the selected set.

    Example::

        rule = ProfitabilityRule()
        result = rule.evaluate(company)
        assert result.rule_id == "AVG_OPERATING_PROFIT_15CR"
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule.

        Returns:
            The string ``"AVG_OPERATING_PROFIT_15CR"``.
        """
        return "AVG_OPERATING_PROFIT_15CR"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for the profitability rule.

        Returns:
            RuleMetadata citing SEBI ICDR Reg. 26(1)(b).
        """
        return RuleMetadata(
            regulation=_REGULATION,
            section=_SECTION,
            clause="Clause (b)",
            description=(
                "Average pre-tax operating profit must be at least ₹15 Crore, "
                "computed across the best 3 of the preceding 5 fiscal years."
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
        return (
            "≥ ₹15 Cr average operating profit across best 3 of "
            "preceding 5 fiscal years"
        )

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate average operating profit over the best 3 of the last 5 FYs.

        Selects the best 3 of up to 5 preceding fiscal years by pre-tax
        operating profit and checks that their average meets the ₹15 Crore
        threshold. Returns INCONCLUSIVE if fewer than 3 years are available
        or if data reliability is insufficient for the selected years.

        Args:
            company: Canonical company data. Must include fiscal year records
                with reliable operating_profit values.

        Returns:
            A RuleResult with verdict PASS, FAIL, or INCONCLUSIVE.
        """
        all_fiscal_years = company.financials.fiscal_years

        # Take the last 5 years from the chronological list (oldest-first)
        window: list[FiscalYear] = list(all_fiscal_years[-_WINDOW:])
        n_available = len(window)

        if n_available < _BEST_OF:
            return self._build_inconclusive(
                reason=(
                    f"only {n_available} fiscal year(s) available; at least "
                    f"{_BEST_OF} years are required to compute the average"
                ),
                actual_value=(
                    f"{n_available} FY(s) available"
                    if window
                    else "no fiscal year data"
                ),
            )

        # Sort descending by operating_profit.value to select the best years.
        # We intentionally sort before reliability check so that low-confidence
        # years outside the top 3 do not trigger INCONCLUSIVE.
        sorted_years = sorted(
            window,
            key=lambda fy: fy.operating_profit.value,
            reverse=True,
        )
        best_three: list[FiscalYear] = sorted_years[:_BEST_OF]

        # Reliability check — only the selected best-3 years must be reliable
        for fy in best_three:
            if not fy.operating_profit.is_reliable():
                return self._build_inconclusive(
                    reason=(
                        f"operating profit for {fy.year_label} (one of the "
                        f"best {_BEST_OF} years) has low confidence without "
                        "human confirmation"
                    ),
                    actual_value=f"unreliable data in {fy.year_label}",
                )

        # Compute the average using exact Decimal arithmetic
        total: Decimal = sum(
            (fy.operating_profit.value for fy in best_three), Decimal("0")
        )
        average: Decimal = total / Decimal(str(_BEST_OF))

        # Build human-readable components
        best_labels = ", ".join(fy.year_label for fy in best_three)
        actual_value = (
            f"{_fmt_crore(average)} average "
            f"(best {_BEST_OF} of {n_available} FYs: {best_labels})"
        )

        if average >= _PROFIT_THRESHOLD:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                explanation=(
                    f"Average pre-tax operating profit of {_fmt_crore(average)} "
                    f"across the best {_BEST_OF} fiscal years ({best_labels}) "
                    f"meets the ₹15 Crore threshold required by ICDR Reg. 26(1)(b)."
                ),
            )

        # FAIL path — compute and format the shortfall
        shortfall: Decimal = _PROFIT_THRESHOLD - average
        gap = (
            f"{_fmt_crore(shortfall)} below the ₹15 Cr threshold "
            f"(current average: {_fmt_crore(average)})"
        )
        explanation = (
            f"Average pre-tax operating profit of {_fmt_crore(average)} "
            f"across the best {_BEST_OF} fiscal years ({best_labels}) "
            f"is below the ₹15 Crore threshold required by ICDR Reg. 26(1)(b). "
            f"Shortfall: {_fmt_crore(shortfall)}."
        )

        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=explanation,
        )
