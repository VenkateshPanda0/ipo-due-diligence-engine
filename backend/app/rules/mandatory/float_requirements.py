"""
backend/app/rules/mandatory/float_requirements.py

Mandatory Rule: Minimum Public Float Offer Percentage.

Implements SEBI (ICDR) Regulations, 2018, Regulation 26(5), which mandates
the minimum percentage of post-issue capital that must be offered to the
public. The threshold is tiered by expected market capitalisation:

  - Market cap ≤ ₹1,600 Cr  →  minimum public offer of 25%
  - Market cap > ₹1,600 Cr  →  minimum public offer of 10%

This rule ensures meaningful public participation and liquidity in newly
listed securities.

This module MUST NOT import from:
  - app.parser, app.api, app.services, app.engine

Import constraint compliance:
  - Imports only from app.models and app.rules.base_rule
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import RuleCategory, Verdict
from app.models.rule_result import RuleMetadata, RuleResult
from app.rules.base_rule import BaseRule

_SEBI_ICDR_REGULATION = "SEBI (ICDR) Regulations, 2018"
_SEBI_ICDR_SOURCE_URL = "https://www.sebi.gov.in/legal/regulations/nov-2018/sebi-icdr-2018.html"

# Market cap threshold (₹ Crores) that determines the applicable float percentage.
_MARKET_CAP_THRESHOLD = Decimal("1600")

# Minimum public offer percentages by market cap tier.
_MIN_OFFER_SMALL_CAP = Decimal("25")   # for market cap ≤ ₹1,600 Cr
_MIN_OFFER_LARGE_CAP = Decimal("10")   # for market cap > ₹1,600 Cr


class FloatRequirementsRule(BaseRule):
    """Mandatory Rule — PUBLIC_OFFER_MIN.

    Enforces the minimum public offer percentage as specified in SEBI (ICDR)
    Regulations, 2018, Regulation 26(5). The required minimum float depends
    on the company's expected post-issue market capitalisation:

    - If ``expected_market_cap ≤ ₹1,600 Cr``:  ``public_offer_percentage ≥ 25%``
    - If ``expected_market_cap > ₹1,600 Cr``:  ``public_offer_percentage ≥ 10%``

    Evaluation logic:
      - If either ``expected_market_cap`` or ``public_offer_percentage`` is not
        reliable, returns INCONCLUSIVE.
      - Selects the applicable minimum threshold based on market cap tier.
      - PASS if ``public_offer_percentage ≥ applicable_minimum``.
      - FAIL otherwise.

    Data sources:
      - ``company.issue_details.expected_market_cap``    — ExtractedValue[Decimal]
      - ``company.issue_details.public_offer_percentage`` — ExtractedValue[Decimal]

    All financial values are in Indian Rupees (₹) in Crore units.
    Percentages are expressed as values between 0 and 100.

    Example::

        >>> rule = FloatRequirementsRule()
        >>> rule.rule_id
        'PUBLIC_OFFER_MIN'
        >>> rule.category.value
        'mandatory'
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for the Float Requirements rule.

        Returns:
            The string ``"PUBLIC_OFFER_MIN"``.
        """
        return "PUBLIC_OFFER_MIN"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for SEBI ICDR Regulation 26(5).

        Returns:
            A frozen RuleMetadata instance citing the minimum public float
            requirement regulation.
        """
        return RuleMetadata(
            regulation=_SEBI_ICDR_REGULATION,
            section="Regulation 26(5)",
            clause=None,
            description=(
                "Minimum public offer percentage: ≥ 25% for market cap ≤ ₹1,600 Cr; "
                "≥ 10% for market cap > ₹1,600 Cr"
            ),
            category=RuleCategory.MANDATORY,
            effective_date=date(2018, 11, 1),
            source_url=_SEBI_ICDR_SOURCE_URL,
        )

    @property
    def _required_value(self) -> str:
        """Human-readable statement of the required threshold.

        Returns:
            A tiered description of the applicable minimum float requirement.
        """
        return (
            "≥ 25% if market cap ≤ ₹1600 Cr; ≥ 10% if market cap > ₹1600 Cr"
        )

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate the public float requirement against CompanyData.

        Determines which market-cap tier applies to the company and checks
        whether the proposed public offer percentage meets the minimum
        required by SEBI (ICDR) Regulations, 2018, Regulation 26(5).

        Args:
            company: The canonical CompanyData object containing issue details.

        Returns:
            A RuleResult with:
              - ``INCONCLUSIVE`` if either data point is unreliable.
              - ``PASS`` if the public offer meets the applicable minimum.
              - ``FAIL`` if the public offer is below the applicable minimum,
                with a gap message specifying the shortfall.
        """
        market_cap_ev = company.issue_details.expected_market_cap
        offer_pct_ev = company.issue_details.public_offer_percentage

        if not market_cap_ev.is_reliable():
            return self._build_inconclusive(
                reason="expected market cap data has insufficient confidence",
                actual_value=None,
            )

        if not offer_pct_ev.is_reliable():
            return self._build_inconclusive(
                reason="public offer percentage data has insufficient confidence",
                actual_value=None,
            )

        market_cap: Decimal = market_cap_ev.value
        offer_pct: Decimal = offer_pct_ev.value

        # Select the applicable minimum based on market cap tier.
        is_small_cap = market_cap <= _MARKET_CAP_THRESHOLD
        min_required: Decimal = _MIN_OFFER_SMALL_CAP if is_small_cap else _MIN_OFFER_LARGE_CAP
        tier_label = (
            f"≤ ₹{_MARKET_CAP_THRESHOLD:,.0f} Cr"
            if is_small_cap
            else f"> ₹{_MARKET_CAP_THRESHOLD:,.0f} Cr"
        )

        actual_value = (
            f"₹{market_cap:.2f} Cr market cap, {offer_pct:.1f}% offered to public"
        )

        if offer_pct >= min_required:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                gap=None,
                explanation=(
                    f"Public offer of {offer_pct:.1f}% meets the minimum {min_required:.0f}% "
                    f"required for a market cap of ₹{market_cap:.2f} Cr "
                    f"(market cap tier: {tier_label}). "
                    "Compliant with SEBI (ICDR) Regulations, 2018, Regulation 26(5)."
                ),
            )

        shortfall: Decimal = min_required - offer_pct
        gap = (
            f"Public offer is {offer_pct:.1f}%; minimum required for market cap "
            f"{tier_label} is {min_required:.0f}%"
        )
        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=(
                f"Public offer percentage of {offer_pct:.1f}% is below the minimum "
                f"{min_required:.0f}% required for a company with expected market cap "
                f"of ₹{market_cap:.2f} Cr (market cap tier: {tier_label}). "
                f"Shortfall: {shortfall:.1f} percentage points. "
                "Fails SEBI (ICDR) Regulations, 2018, Regulation 26(5)."
            ),
        )
