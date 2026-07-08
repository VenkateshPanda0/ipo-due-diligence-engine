"""
backend/app/engine/gap_planner.py

Gap Planner — M4-006.

Generates GapAnalysisItem for every failed mandatory rule. Each item
quantifies the shortfall, projects the earliest fiscal year when the company
could become eligible, and provides rule-specific remediation steps.

ARCHITECTURAL CONSTRAINTS:
  - May import from: models/ only
  - MUST NOT import from: parser/, api/, services/
  - Pure computation: no I/O, no side effects.
  - Uses linear trend projection (not CAGR) for FY estimates per roadmap.

Design:
  - The GapPlanner is stateless.
  - Gap projection uses the most recent 2 fiscal years' operating profit
    to estimate annual growth and project when the threshold will be reached.
  - Rule-specific remediation steps are hard-coded by rule_id.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.ipo_report import GapAnalysisItem
from app.models.rule_result import RuleResult

# Rule-specific remediation steps indexed by rule_id.
_REMEDIATION_STEPS: dict[str, list[str]] = {
    "NTA_3CR": [
        "Increase net tangible assets to ≥ ₹3 Crore in each of the three preceding FYs.",
        "Infuse equity capital or retain profits to build tangible asset base.",
        "Dispose of intangible-heavy assets or liabilities that reduce NTA.",
        "Ensure all balance sheet items are correctly classified per Ind AS.",
    ],
    "MONETARY_ASSETS_50PCT": [
        "Deploy excess cash into productive tangible assets (plant, equipment, inventory).",
        "Reduce cash and FD holdings relative to total NTA.",
        "Invest in capital expenditure that adds tangible value to the business.",
        "Review asset classification to ensure monetary assets are correctly identified.",
    ],
    "AVG_OPERATING_PROFIT_15CR": [
        "Grow revenue by expanding customer base, increasing pricing, or entering new markets.",
        "Improve operating margins through cost optimisation and operational efficiency.",
        "Target operating profit of ≥ ₹15 Crore in each of the next 3 fiscal years.",
        "Reduce fixed costs and overheads that compress operating profit margins.",
    ],
    "NET_WORTH_1CR": [
        "Raise equity capital through rights issue, private placement, or promoter infusion.",
        "Retain profits to build reserves and surplus.",
        "Avoid dividend payouts that would reduce net worth below the ₹1 Crore threshold.",
        "Reverse accumulated losses through sustained profitability over multiple years.",
    ],
    "ISSUE_SIZE_5X": [
        "Reduce the proposed issue size to be within 5× of pre-issue net worth.",
        "Build net worth through profit retention before filing the DRHP.",
        "Consider a phased fundraising approach with a smaller initial issue.",
        "Raise pre-IPO equity from private investors to increase the net worth base.",
    ],
    "TRACK_RECORD_3Y": [
        "Continue operating until 3 full fiscal years of audited accounts are available.",
        "Ensure audited financial statements cover each full fiscal year since incorporation.",
        "Consider restructuring to ensure the operating entity has ≥ 3 FYs of track record.",
        "Engage a Big 4 or reputable auditor to audit all 3 preceding fiscal years.",
    ],
    "PUBLIC_OFFER_MIN": [
        "Increase the public float to meet the minimum threshold (25% or 10% based on market cap).",
        "Adjust the offer size to ensure at least 25% of post-issue capital is offered publicly.",
        "Review expected market capitalisation to confirm which float threshold applies.",
        "Consult SEBI guidelines on minimum public shareholding requirements.",
    ],
    "PROMOTER_CONTRIBUTION_20": [
        "Ensure promoters retain ≥ 20% of post-issue paid-up capital.",
        "Reduce the Offer for Sale portion to preserve promoter holding above 20%.",
        "If promoter holding will fall below 20%, seek anchor investor commitments.",
        "Review the capital structure to ensure post-issue promoter holding is compliant.",
    ],
    "PROMOTER_LOCK_IN": [
        "Commit to the required lock-in period (18 months standard, 36 months for capex issues).",
        "Document lock-in commitments clearly in the DRHP.",
        "Ensure all promoter entities are included in the lock-in undertaking.",
        "Obtain legal opinion confirming the lock-in structure complies with SEBI ICDR.",
    ],
    "MIN_POST_ISSUE_CAPITAL": [
        "Ensure post-issue paid-up capital will be ≥ ₹10 Crore after the IPO.",
        "Increase the fresh issue component to raise paid-up capital to the required level.",
        "Review the capital structure and share price to meet the paid-up capital threshold.",
        "Consider a bonus issue or subdivision of shares to achieve the required capital base.",
    ],
    "MIN_MARKET_CAP": [
        "Ensure expected market capitalisation at issue price is ≥ ₹25 Crore.",
        "Review issue price and shares outstanding to confirm market cap projection.",
        "Build the business to a scale where a ₹25 Crore market cap is achievable.",
        "Engage SEBI-registered investment bankers to correctly estimate market capitalisation.",
    ],
}


def _get_latest_fy_label(company: CompanyData) -> str:
    """Return the label of the most recent fiscal year."""
    if company.financials.fiscal_years:
        return company.financials.fiscal_years[-1].year_label
    return "Unknown"


def _project_earliest_eligible_fy(
    rule_id: str,
    company: CompanyData,
) -> str:
    """Project the earliest fiscal year when the company could become eligible.

    Uses a simple linear trend projection based on the last 2 fiscal years'
    data. If insufficient data exists for projection, returns "Undetermined".

    Currently implemented for AVG_OPERATING_PROFIT_15CR with linear profit
    growth extrapolation. All other rules return "Undetermined".

    Args:
        rule_id: The rule that failed.
        company: The canonical company data.

    Returns:
        A fiscal year label string such as "FY2027", or "Undetermined".
    """
    if rule_id != "AVG_OPERATING_PROFIT_15CR":
        return "Undetermined"

    years = company.financials.fiscal_years
    if len(years) < 2:
        return "Undetermined"

    try:
        latest = years[-1].operating_profit.value
        prev = years[-2].operating_profit.value
        annual_growth = latest - prev

        if annual_growth <= Decimal("0"):
            return "Undetermined"

        # Extract the fiscal year number from the label (e.g. "FY2024" → 2024)
        latest_label = years[-1].year_label
        year_str = latest_label.replace("FY", "").split("-")[0]
        current_fy = int(year_str)

        # Project forward using average of best 3
        threshold = Decimal("15")
        current_profit = latest
        for years_ahead in range(1, 11):
            current_profit += annual_growth
            avg = current_profit  # simplification: if all 3 future years at this level
            if avg >= threshold:
                return f"FY{current_fy + years_ahead}"

        return "Undetermined"
    except (ValueError, ZeroDivisionError, AttributeError):
        return "Undetermined"


class GapPlanner:
    """Generates GapAnalysisItem for every failed mandatory rule.

    The GapPlanner is stateless. Given a set of rule results and the
    company data, it produces GapAnalysisItem objects for every failed
    mandatory rule. Each item contains the gap size (from the RuleResult),
    an FY projection, and rule-specific remediation steps.

    Example::

        planner = GapPlanner()
        gap_items = planner.generate(results, company)
        assert all(item.rule_id in [r.rule_id for r in results] for item in gap_items)
    """

    def generate(
        self,
        results: list[RuleResult],
        company: CompanyData,
    ) -> list[GapAnalysisItem]:
        """Generate GapAnalysisItem for every failed mandatory rule.

        Args:
            results: All RuleResult objects from the Rules Engine.
            company: The canonical company data used for projection.

        Returns:
            List of GapAnalysisItem, one per failed mandatory rule,
            in the same order as the results list.
        """
        from app.models.enums import RuleCategory
        items: list[GapAnalysisItem] = []
        for result in results:
            if (
                result.category == RuleCategory.MANDATORY
                and result.verdict == Verdict.FAIL
            ):
                item = self._build_gap_item(result, company)
                items.append(item)
        return items

    def _build_gap_item(
        self,
        result: RuleResult,
        company: CompanyData,
    ) -> GapAnalysisItem:
        """Build a GapAnalysisItem from a failed mandatory RuleResult.

        Args:
            result: A failed mandatory RuleResult.
            company: The canonical company data.

        Returns:
            A fully constructed GapAnalysisItem.
        """
        earliest_fy = _project_earliest_eligible_fy(result.rule_id, company)
        remediation = _REMEDIATION_STEPS.get(
            result.rule_id,
            [
                "Review the specific regulatory requirement and consult your "
                "SEBI-registered merchant banker.",
                "Engage legal and financial advisors to develop a remediation plan.",
            ],
        )

        return GapAnalysisItem(
            rule_id=result.rule_id,
            gap_size=result.gap or "Gap not quantified — see explanation.",
            earliest_eligible_fy=earliest_fy,
            remediation_steps=remediation,
            current_value=result.actual_value or "Not available",
            required_value=result.required_value,
        )
