"""
backend/app/rules/mandatory/net_tangible_assets.py

SEBI ICDR Regulation 26(1)(a) — Net Tangible Assets & Monetary Assets rules.

This module implements two closely related mandatory eligibility rules:

  1. NTARule (NTA_3CR):
     The company must have net tangible assets of at least ₹3 Crore in each
     of the three preceding full fiscal years. A shortfall in even one year
     causes a FAIL.

  2. MonetaryAssetsRule (MONETARY_ASSETS_50PCT):
     Monetary assets (cash, fixed deposits, bank balances) must not exceed
     50% of net tangible assets in any of the three preceding full fiscal
     years. Excessive liquidity relative to NTA signals that the company
     may not have deployed capital productively.

Both rules examine the LAST 3 fiscal years in CompanyData.financials.fiscal_years
(stored oldest-first). If fewer than 3 years are available, or if any required
ExtractedValue is not reliable, both rules return INCONCLUSIVE — never FAIL —
because a data gap is not the same as a regulatory breach.

Regulation: SEBI (ICDR) Regulations, 2018, Regulation 26(1), Clause (a)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.company_data import CompanyData, FiscalYear
from app.models.enums import RuleCategory, Verdict
from app.models.rule_result import RuleMetadata, RuleResult
from app.rules.base_rule import BaseRule

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_NTA_THRESHOLD = Decimal("3")        # ₹3 Crore
_MONETARY_PCT_LIMIT = Decimal("50")  # 50% of NTA
_CRORE_SUFFIX = " Cr"
_REGULATION = "SEBI (ICDR) Regulations, 2018"
_SECTION = "Regulation 26(1)"
_EFFECTIVE_DATE = date(2018, 11, 1)
_SOURCE_URL = (
    "https://www.sebi.gov.in/legal/regulations/nov-2018/"
    "sebi-icdr-regulations-2018.html"
)


def _fmt_crore(value: Decimal) -> str:
    """Format a Decimal crore value as '₹X.XX Cr'."""
    return f"₹{value:.2f}{_CRORE_SUFFIX}"


def _fmt_pct(value: Decimal) -> str:
    """Format a Decimal percentage as 'X.XX%'."""
    return f"{value:.2f}%"


class NTARule(BaseRule):
    """Mandatory rule: Net Tangible Assets ≥ ₹3 Crore in each of 3 preceding FYs.

    SEBI (ICDR) Regulations, 2018, Regulation 26(1), Clause (a) requires that
    a company seeking mainboard listing must have net tangible assets of at least
    ₹3 Crore in each of the three preceding full fiscal years.

    Evaluation logic:
      - Requires the last 3 fiscal years from CompanyData.financials.fiscal_years.
      - Returns INCONCLUSIVE if fewer than 3 years are available.
      - Returns INCONCLUSIVE if any year's net_tangible_assets ExtractedValue
        is not reliable (confidence=LOW without human confirmation).
      - Returns FAIL if any year has NTA < ₹3 Crore, with a gap message
        identifying the worst shortfall year.
      - Returns PASS only when all 3 years meet the threshold.

    Example::

        rule = NTARule()
        result = rule.evaluate(company)
        assert result.rule_id == "NTA_3CR"
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule.

        Returns:
            The string ``"NTA_3CR"``.
        """
        return "NTA_3CR"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for the NTA rule.

        Returns:
            RuleMetadata citing SEBI ICDR Reg. 26(1)(a) as the source.
        """
        return RuleMetadata(
            regulation=_REGULATION,
            section=_SECTION,
            clause="Clause (a)",
            description=(
                "Net tangible assets must be at least ₹3 Crore in each of "
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
        return "≥ ₹3 Cr NTA in each of the 3 preceding full fiscal years"

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate NTA compliance across the last 3 fiscal years.

        Checks that net_tangible_assets ≥ ₹3 Crore for each of the three
        most recent fiscal years. Returns INCONCLUSIVE if data is missing
        or unreliable; FAIL if any year falls short; PASS otherwise.

        Args:
            company: Canonical company data. Must include at least 3 fiscal
                years with reliable net_tangible_assets values.

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

        # Reliability check — do this before any value comparisons
        for fy in last_three:
            if not fy.net_tangible_assets.is_reliable():
                return self._build_inconclusive(
                    reason=(
                        f"net tangible assets for {fy.year_label} have "
                        "low confidence without human confirmation"
                    ),
                    actual_value=f"unreliable data in {fy.year_label}",
                )

        # Evaluate each year against the ₹3 Crore threshold
        failing_years: list[tuple[str, Decimal]] = []
        year_summaries: list[str] = []

        for fy in last_three:
            nta: Decimal = fy.net_tangible_assets.value
            year_summaries.append(f"{fy.year_label}: {_fmt_crore(nta)}")
            if nta < _NTA_THRESHOLD:
                failing_years.append((fy.year_label, nta))

        actual_value = "; ".join(year_summaries)

        if not failing_years:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                explanation=(
                    "Net tangible assets met the ₹3 Crore threshold in all "
                    f"three preceding fiscal years: {actual_value}."
                ),
            )

        # Identify the worst shortfall year for the gap message
        worst_label, worst_nta = min(failing_years, key=lambda t: t[1])
        shortfall: Decimal = _NTA_THRESHOLD - worst_nta
        gap = (
            f"{_fmt_crore(shortfall)} below ₹3 Cr threshold in {worst_label}"
        )

        failed_labels = ", ".join(label for label, _ in failing_years)
        explanation = (
            f"Net tangible assets fell below the ₹3 Crore threshold in "
            f"{len(failing_years)} of 3 fiscal year(s): {failed_labels}. "
            f"Actual values — {actual_value}. "
            f"Worst shortfall: {_fmt_crore(worst_nta)} in {worst_label} "
            f"({_fmt_crore(shortfall)} below the ₹3 Cr minimum)."
        )

        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=explanation,
        )


class MonetaryAssetsRule(BaseRule):
    """Mandatory rule: Monetary assets ≤ 50% of NTA in each of 3 preceding FYs.

    The proviso to SEBI (ICDR) Regulations, 2018, Regulation 26(1), Clause (a)
    restricts monetary assets to no more than 50% of the company's net tangible
    assets in each of the three preceding full fiscal years. This prevents
    companies from qualifying on the strength of cash holdings alone.

    Special cases:
      - If NTA is zero or negative and monetary assets > 0: that year FAILS
        (the ratio is effectively infinite / undefined but the company is
        holding cash against no or negative tangible base).
      - If NTA is zero and monetary assets = 0: that year is treated as a PASS
        (no cash, no tangible assets — ratio is 0%).

    Evaluation logic:
      - Requires the last 3 fiscal years.
      - Returns INCONCLUSIVE if fewer than 3 years are available.
      - Returns INCONCLUSIVE if net_tangible_assets or monetary_assets for
        any year are not reliable.
      - Returns FAIL if any year has monetary assets > 50% of NTA.
      - Returns PASS if all 3 years comply.

    Example::

        rule = MonetaryAssetsRule()
        result = rule.evaluate(company)
        assert result.rule_id == "MONETARY_ASSETS_50PCT"
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule.

        Returns:
            The string ``"MONETARY_ASSETS_50PCT"``.
        """
        return "MONETARY_ASSETS_50PCT"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for the monetary assets rule.

        Returns:
            RuleMetadata citing SEBI ICDR Reg. 26(1)(a) Proviso.
        """
        return RuleMetadata(
            regulation=_REGULATION,
            section=_SECTION,
            clause="Clause (a) Proviso",
            description=(
                "Monetary assets must not exceed 50% of net tangible assets "
                "in each of the three preceding full fiscal years."
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
            "Monetary assets ≤ 50% of NTA in each of the "
            "3 preceding full fiscal years"
        )

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate monetary asset concentration across the last 3 fiscal years.

        Calculates monetary_assets / NTA for each of the three most recent
        fiscal years. Returns INCONCLUSIVE if data is missing or unreliable;
        FAIL if any year exceeds 50%; PASS otherwise.

        Args:
            company: Canonical company data. Must include at least 3 fiscal
                years with reliable net_tangible_assets and monetary_assets.

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

        # Reliability check for both NTA and monetary assets before computation
        for fy in last_three:
            if not fy.net_tangible_assets.is_reliable():
                return self._build_inconclusive(
                    reason=(
                        f"net tangible assets for {fy.year_label} have "
                        "low confidence without human confirmation"
                    ),
                    actual_value=f"unreliable NTA data in {fy.year_label}",
                )
            if not fy.monetary_assets.is_reliable():
                return self._build_inconclusive(
                    reason=(
                        f"monetary assets for {fy.year_label} have "
                        "low confidence without human confirmation"
                    ),
                    actual_value=(
                        f"unreliable monetary asset data in {fy.year_label}"
                    ),
                )

        # Compute ratios and detect failures
        failing_years: list[tuple[str, Decimal]] = []
        year_summaries: list[str] = []

        for fy in last_three:
            nta: Decimal = fy.net_tangible_assets.value
            monetary: Decimal = fy.monetary_assets.value

            if nta <= Decimal("0"):
                if monetary > Decimal("0"):
                    # NTA is zero/negative but monetary assets exist: automatic FAIL
                    # Represent ratio as > 100% for messaging purposes
                    ratio = Decimal("100")
                    failing_years.append((fy.year_label, ratio))
                    year_summaries.append(
                        f"{fy.year_label}: {_fmt_crore(monetary)} monetary vs "
                        f"{_fmt_crore(nta)} NTA (ratio undefined / >100%)"
                    )
                else:
                    # Both zero: treat as 0% ratio — PASS for this year
                    ratio = Decimal("0")
                    year_summaries.append(
                        f"{fy.year_label}: {_fmt_pct(ratio)} (both monetary "
                        "assets and NTA are zero)"
                    )
            else:
                ratio = (monetary / nta) * Decimal("100")
                year_summaries.append(
                    f"{fy.year_label}: {_fmt_pct(ratio)} "
                    f"({_fmt_crore(monetary)} / {_fmt_crore(nta)})"
                )
                if ratio > _MONETARY_PCT_LIMIT:
                    failing_years.append((fy.year_label, ratio))

        actual_value = "; ".join(year_summaries)

        if not failing_years:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                explanation=(
                    "Monetary assets remained within the 50% of NTA limit in "
                    f"all three preceding fiscal years: {actual_value}."
                ),
            )

        # Build gap using the worst (highest ratio) failing year
        worst_label, worst_ratio = max(failing_years, key=lambda t: t[1])
        gap = (
            f"Monetary assets were {_fmt_pct(worst_ratio)} of NTA in "
            f"{worst_label} (limit: 50%)"
        )

        failed_labels = ", ".join(label for label, _ in failing_years)
        explanation = (
            f"Monetary assets exceeded 50% of NTA in "
            f"{len(failing_years)} of 3 fiscal year(s): {failed_labels}. "
            f"Year-by-year ratios — {actual_value}. "
            f"Worst breach: {_fmt_pct(worst_ratio)} in {worst_label} "
            f"(limit is 50%)."
        )

        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=explanation,
        )
