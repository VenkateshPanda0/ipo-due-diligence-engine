"""
backend/app/rules/mandatory/issue_size.py

Mandatory Rule: Issue Size ≤ 5× Pre-Issue Net Worth.

Implements SEBI (ICDR) Regulations, 2018, Regulation 26(2), which restricts
the total issue size to a maximum of five times the company's pre-issue net
worth. This guard prevents over-leveraged issues where an issuer would raise
capital far exceeding their existing equity base.

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
_MAX_MULTIPLIER = Decimal("5")


class IssueSizeRule(BaseRule):
    """Mandatory Rule — ISSUE_SIZE_5X.

    Enforces that the total IPO issue size does not exceed five times the
    company's pre-issue net worth, as required by SEBI (ICDR) Regulations,
    2018, Regulation 26(2).

    Evaluation logic:
      - If either ``issue_size`` or ``pre_issue_net_worth`` is not reliable
        (low confidence, unconfirmed), the rule returns INCONCLUSIVE.
      - If ``pre_issue_net_worth`` ≤ 0, the rule returns FAIL immediately.
        A non-positive net worth makes the ratio undefined and is itself a
        disqualifying condition.
      - PASS if ``issue_size ≤ 5 × pre_issue_net_worth`` (exactly 5× is allowed).
      - FAIL if ``issue_size > 5 × pre_issue_net_worth``.

    Data sources:
      - ``company.issue_details.issue_size``        — ExtractedValue[Decimal]
      - ``company.issue_details.pre_issue_net_worth`` — ExtractedValue[Decimal]

    All financial values are in Indian Rupees (₹) in Crore units.

    Example::

        >>> rule = IssueSizeRule()
        >>> rule.rule_id
        'ISSUE_SIZE_5X'
        >>> rule.category.value
        'mandatory'
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for the Issue Size rule.

        Returns:
            The string ``"ISSUE_SIZE_5X"``.
        """
        return "ISSUE_SIZE_5X"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for SEBI ICDR Regulation 26(2).

        Returns:
            A frozen RuleMetadata instance citing the exact regulation and
            section under which the issue size constraint is imposed.
        """
        return RuleMetadata(
            regulation=_SEBI_ICDR_REGULATION,
            section="Regulation 26(2)",
            clause=None,
            description="Total issue size must not exceed 5× the pre-issue net worth",
            category=RuleCategory.MANDATORY,
            effective_date=date(2018, 11, 1),
            source_url=_SEBI_ICDR_SOURCE_URL,
        )

    @property
    def _required_value(self) -> str:
        """Human-readable statement of the required threshold.

        Returns:
            The string ``"Issue size ≤ 5× pre-issue net worth"``.
        """
        return "Issue size ≤ 5× pre-issue net worth"

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate the issue size constraint against CompanyData.

        Checks that the total IPO issue size does not exceed five times the
        pre-issue net worth of the issuing company.

        Args:
            company: The canonical CompanyData object containing issue details.

        Returns:
            A RuleResult with:
              - ``INCONCLUSIVE`` if either data point is unreliable.
              - ``FAIL`` if pre-issue net worth ≤ 0, or if issue size exceeds
                the 5× limit.
              - ``PASS`` if issue size ≤ 5 × pre-issue net worth.
        """
        issue_size_ev = company.issue_details.issue_size
        net_worth_ev = company.issue_details.pre_issue_net_worth

        if not issue_size_ev.is_reliable():
            return self._build_inconclusive(
                reason="issue size data has insufficient confidence",
                actual_value=None,
            )

        if not net_worth_ev.is_reliable():
            return self._build_inconclusive(
                reason="pre-issue net worth data has insufficient confidence",
                actual_value=None,
            )

        issue_size: Decimal = issue_size_ev.value
        net_worth: Decimal = net_worth_ev.value

        # Non-positive net worth: ratio is undefined and itself disqualifying.
        if net_worth <= Decimal("0"):
            return self._build_result(
                verdict=Verdict.FAIL,
                actual_value=(
                    f"₹{issue_size:.2f} Cr issue size vs "
                    f"₹{net_worth:.2f} Cr pre-issue net worth"
                ),
                gap=(
                    "Pre-issue net worth is ≤ 0 — ratio cannot be computed; "
                    "issue size rule cannot be satisfied."
                ),
                explanation=(
                    f"Pre-issue net worth of ₹{net_worth:.2f} Cr is non-positive. "
                    "The 5× issue size limit requires a positive net worth base. "
                    "This represents a fundamental eligibility failure under "
                    "SEBI (ICDR) Regulations, 2018, Regulation 26(2)."
                ),
            )

        limit: Decimal = _MAX_MULTIPLIER * net_worth
        ratio: Decimal = issue_size / net_worth

        actual_value = (
            f"₹{issue_size:.2f} Cr issue size vs "
            f"₹{net_worth:.2f} Cr pre-issue net worth (ratio: {ratio:.2f}x)"
        )

        if issue_size <= limit:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                gap=None,
                explanation=(
                    f"Issue size of ₹{issue_size:.2f} Cr is within the permitted "
                    f"5× limit of ₹{limit:.2f} Cr (5 × ₹{net_worth:.2f} Cr). "
                    f"Ratio: {ratio:.2f}x. Compliant with SEBI (ICDR) Regulations, "
                    "2018, Regulation 26(2)."
                ),
            )

        gap = (
            f"Issue size (₹{issue_size:.2f} Cr) exceeds 5× pre-issue net worth "
            f"(₹{net_worth:.2f} Cr × 5 = ₹{limit:.2f} Cr)"
        )
        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=(
                f"Issue size of ₹{issue_size:.2f} Cr exceeds the maximum permitted "
                f"5× pre-issue net worth limit of ₹{limit:.2f} Cr "
                f"(5 × ₹{net_worth:.2f} Cr). Current ratio: {ratio:.2f}x, "
                f"which is {ratio - _MAX_MULTIPLIER:.2f}x above the 5× ceiling. "
                "Fails SEBI (ICDR) Regulations, 2018, Regulation 26(2)."
            ),
        )
