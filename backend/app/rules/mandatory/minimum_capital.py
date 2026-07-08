"""
backend/app/rules/mandatory/minimum_capital.py

Mandatory Rules: Minimum Post-Issue Capital and Minimum Market Capitalisation.

Implements two NSE/BSE listing requirement rules:

  1. MinPostIssueCapitalRule (MIN_POST_ISSUE_CAPITAL):
     Post-issue paid-up capital must be ≥ ₹10 Crores.

  2. MinMarketCapRule (MIN_MARKET_CAP):
     Expected market capitalisation must be ≥ ₹25 Crores.

These rules enforce the stock exchange floor requirements for minimum company
size at the time of listing, ensuring adequate investor protection through
market depth and liquidity.

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

_LISTING_REGULATION = "NSE/BSE Listing Requirements"
_MIN_POST_ISSUE_CAPITAL = Decimal("10")   # ₹10 Crores
_MIN_MARKET_CAP = Decimal("25")           # ₹25 Crores


class MinPostIssueCapitalRule(BaseRule):
    """Mandatory Rule — MIN_POST_ISSUE_CAPITAL.

    Enforces that the post-issue paid-up share capital of the company is at
    least ₹10 Crores, as required by NSE/BSE listing regulations.

    This floor ensures the issuer has a sufficiently large capital base to
    support meaningful public shareholding and secondary-market liquidity
    post-listing.

    Evaluation logic:
      - If ``post_issue_paid_up_capital`` is not reliable, returns INCONCLUSIVE.
      - PASS if ``post_issue_paid_up_capital ≥ ₹10 Cr``.
      - FAIL otherwise, with a gap message quantifying the shortfall.

    Data source:
      - ``company.issue_details.post_issue_paid_up_capital`` — ExtractedValue[Decimal]

    All financial values are in Indian Rupees (₹) in Crore units.

    Example::

        >>> rule = MinPostIssueCapitalRule()
        >>> rule.rule_id
        'MIN_POST_ISSUE_CAPITAL'
        >>> rule.category.value
        'mandatory'
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for the Minimum Post-Issue Capital rule.

        Returns:
            The string ``"MIN_POST_ISSUE_CAPITAL"``.
        """
        return "MIN_POST_ISSUE_CAPITAL"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for the NSE/BSE minimum paid-up capital requirement.

        Returns:
            A frozen RuleMetadata instance citing the stock exchange listing
            requirement that imposes a ₹10 Cr floor on post-issue paid-up capital.
        """
        return RuleMetadata(
            regulation=_LISTING_REGULATION,
            section="Minimum Capital Requirement",
            clause=None,
            description=(
                "Post-issue paid-up capital must be at least ₹10 Crores"
            ),
            category=RuleCategory.MANDATORY,
            effective_date=date(2015, 9, 2),
            source_url=None,
        )

    @property
    def _required_value(self) -> str:
        """Human-readable statement of the required threshold.

        Returns:
            The string ``"Post-issue paid-up capital ≥ ₹10 Cr"``.
        """
        return "Post-issue paid-up capital ≥ ₹10 Cr"

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate the minimum post-issue paid-up capital against CompanyData.

        Checks that the total post-issue paid-up capital of the company meets
        the ₹10 Crore floor imposed by NSE/BSE listing requirements.

        Args:
            company: The canonical CompanyData object containing issue details.

        Returns:
            A RuleResult with:
              - ``INCONCLUSIVE`` if the paid-up capital data is unreliable.
              - ``PASS`` if post-issue paid-up capital ≥ ₹10 Cr.
              - ``FAIL`` if below the threshold, with a gap message.
        """
        capital_ev = company.issue_details.post_issue_paid_up_capital

        if not capital_ev.is_reliable():
            return self._build_inconclusive(
                reason="post-issue paid-up capital data has insufficient confidence",
                actual_value=None,
            )

        capital: Decimal = capital_ev.value
        actual_value = f"₹{capital:.2f} Cr post-issue paid-up capital"

        if capital >= _MIN_POST_ISSUE_CAPITAL:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                gap=None,
                explanation=(
                    f"Post-issue paid-up capital of ₹{capital:.2f} Cr meets the "
                    f"minimum ₹{_MIN_POST_ISSUE_CAPITAL:.0f} Cr required by "
                    "NSE/BSE listing requirements."
                ),
            )

        shortfall: Decimal = _MIN_POST_ISSUE_CAPITAL - capital
        gap = (
            f"Post-issue paid-up capital (₹{capital:.2f} Cr) is below the "
            f"required ₹{_MIN_POST_ISSUE_CAPITAL:.0f} Cr"
        )
        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=(
                f"Post-issue paid-up capital of ₹{capital:.2f} Cr is "
                f"₹{shortfall:.2f} Cr below the minimum ₹{_MIN_POST_ISSUE_CAPITAL:.0f} Cr "
                "floor imposed by NSE/BSE listing requirements. The company must "
                "increase its paid-up capital through fresh equity issuance to "
                "meet this threshold before pursuing an IPO."
            ),
        )


class MinMarketCapRule(BaseRule):
    """Mandatory Rule — MIN_MARKET_CAP.

    Enforces that the expected post-issue market capitalisation is at least
    ₹25 Crores, as required by NSE/BSE listing regulations.

    This floor ensures that only companies of sufficient market scale access
    the public markets, providing a reasonable basis for investor participation
    and secondary market activity.

    Evaluation logic:
      - If ``expected_market_cap`` is not reliable, returns INCONCLUSIVE.
      - PASS if ``expected_market_cap ≥ ₹25 Cr``.
      - FAIL otherwise, with a gap message quantifying the shortfall.

    Data source:
      - ``company.issue_details.expected_market_cap`` — ExtractedValue[Decimal]

    All financial values are in Indian Rupees (₹) in Crore units.

    Example::

        >>> rule = MinMarketCapRule()
        >>> rule.rule_id
        'MIN_MARKET_CAP'
        >>> rule.category.value
        'mandatory'
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for the Minimum Market Cap rule.

        Returns:
            The string ``"MIN_MARKET_CAP"``.
        """
        return "MIN_MARKET_CAP"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for the NSE/BSE minimum market cap requirement.

        Returns:
            A frozen RuleMetadata instance citing the stock exchange listing
            requirement that imposes a ₹25 Cr floor on expected market cap.
        """
        return RuleMetadata(
            regulation=_LISTING_REGULATION,
            section="Minimum Market Capitalisation Requirement",
            clause=None,
            description=(
                "Expected market capitalisation must be at least ₹25 Crores"
            ),
            category=RuleCategory.MANDATORY,
            effective_date=date(2015, 9, 2),
            source_url=None,
        )

    @property
    def _required_value(self) -> str:
        """Human-readable statement of the required threshold.

        Returns:
            The string ``"Expected market capitalisation ≥ ₹25 Cr"``.
        """
        return "Expected market capitalisation ≥ ₹25 Cr"

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate the minimum expected market capitalisation against CompanyData.

        Checks that the expected post-issue market capitalisation meets the
        ₹25 Crore floor imposed by NSE/BSE listing requirements.

        Args:
            company: The canonical CompanyData object containing issue details.

        Returns:
            A RuleResult with:
              - ``INCONCLUSIVE`` if the market cap data is unreliable.
              - ``PASS`` if expected market cap ≥ ₹25 Cr.
              - ``FAIL`` if below the threshold, with a gap message.
        """
        market_cap_ev = company.issue_details.expected_market_cap

        if not market_cap_ev.is_reliable():
            return self._build_inconclusive(
                reason="expected market cap data has insufficient confidence",
                actual_value=None,
            )

        market_cap: Decimal = market_cap_ev.value
        actual_value = f"₹{market_cap:.2f} Cr expected market capitalisation"

        if market_cap >= _MIN_MARKET_CAP:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                gap=None,
                explanation=(
                    f"Expected market capitalisation of ₹{market_cap:.2f} Cr meets "
                    f"the minimum ₹{_MIN_MARKET_CAP:.0f} Cr required by NSE/BSE "
                    "listing requirements."
                ),
            )

        shortfall: Decimal = _MIN_MARKET_CAP - market_cap
        gap = (
            f"Expected market cap (₹{market_cap:.2f} Cr) is below the "
            f"required ₹{_MIN_MARKET_CAP:.0f} Cr"
        )
        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=(
                f"Expected market capitalisation of ₹{market_cap:.2f} Cr is "
                f"₹{shortfall:.2f} Cr below the minimum ₹{_MIN_MARKET_CAP:.0f} Cr "
                "floor imposed by NSE/BSE listing requirements. The issue price or "
                "post-issue capital structure must be revised to achieve the required "
                "market capitalisation threshold."
            ),
        )
