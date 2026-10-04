"""
backend/app/rules/mandatory/float_requirements.py

Minimum public offer — Securities Contracts (Regulation) Rules, 1957, Rule
19(2)(b) as substituted by G.S.R. 184(E) dated 13 March 2026 (six tiers).

Tier selection uses post-issue capital at the offer price ``M`` (₹ crore); upper
bounds are inclusive. Offer value ``V = M × p / 100``.

  1. M ≤ 1,600           p ≥ 25 %
  2. 1,600 < M ≤ 4,000    V ≥ 400
  3. 4,000 < M ≤ 50,000   p ≥ 10 %
  4. 50,000 < M ≤ 1,00,000      V ≥ 1,000 and p ≥ 8 %
  5. 1,00,000 < M ≤ 5,00,000    V ≥ 6,250 and p ≥ 2.75 %
  6. M > 5,00,000         V ≥ 15,000 and p ≥ 1 %, and p ≥ 2.5 %

Primary gazette text was not retrieved (see sources register); tiers 4-6 are
flagged for human review. Secondary summaries of tier 6 mention both 1 % and
2.5 %: an offer below 1 % fails, but one between 1 % and 2.5 % is sent for human
review rather than failed, because the stricter reading is an interpretation.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs, fmt_crore, fmt_pct


class FloatRequirementsRule(BaseRule):
    """Minimum public offer per SCRR Rule 19(2)(b) (2026 tiers)."""

    rule_id = "PUBLIC_OFFER_MIN"

    @property
    def required_value(self) -> str:
        return (
            "Minimum public offer per the applicable SCRR Rule 19(2)(b) tier (post-issue "
            "capital at offer price)"
        )

    def tier_requirements(self, market_cap: Decimal) -> tuple[int, Decimal | None, Decimal | None]:
        """Return (tier, minimum offer value ₹ Cr or None, minimum offer % or None)."""
        s = self.spec
        if market_cap <= s.decimal("tier1_max_crore"):
            return 1, None, s.decimal("tier1_min_pct")
        if market_cap <= s.decimal("tier2_max_crore"):
            return 2, s.decimal("tier2_min_value_crore"), None
        if market_cap <= s.decimal("tier3_max_crore"):
            return 3, None, s.decimal("tier3_min_pct")
        if market_cap <= s.decimal("tier4_max_crore"):
            return 4, s.decimal("tier4_min_value_crore"), s.decimal("tier4_min_pct")
        if market_cap <= s.decimal("tier5_max_crore"):
            return 5, s.decimal("tier5_min_value_crore"), s.decimal("tier5_min_pct")
        return 6, s.decimal("tier6_min_value_crore"), s.decimal("tier6_min_pct")

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        issue = company.issue_details
        market_cap = inputs.get("issue_details.expected_market_cap", issue.expected_market_cap)
        pct = inputs.get("issue_details.public_offer_percentage", issue.public_offer_percentage)
        if market_cap is None or pct is None or inputs.unreliable:
            return self._undetermined(inputs)
        if market_cap <= 0:
            inputs.calc(
                f"Post-issue capital at offer price {fmt_crore(market_cap)} is not positive."
            )
            return self._result(
                Verdict.REQUIRES_HUMAN_REVIEW,
                inputs,
                explanation="Post-issue capital at offer price must be positive to select a tier.",
                review_reasons=["Implausible post-issue market capitalisation."],
            )
        tier, min_value, min_pct = self.tier_requirements(market_cap)
        offer_value = market_cap * pct / Decimal(100)
        inputs.calc(f"Tier {tier}: post-issue capital at offer price {fmt_crore(market_cap)}")
        inputs.calc(
            f"Offer value = {fmt_crore(market_cap)} × {fmt_pct(pct)} = {fmt_crore(offer_value)}"
        )
        inputs.calculated("issue_details.public_offer_value", f"{offer_value:.4f}", "INR_CRORE")

        shortfalls: list[str] = []
        required_parts: list[str] = []
        if min_value is not None:
            required_parts.append(f"offer value ≥ {fmt_crore(min_value)}")
            if offer_value < min_value:
                shortfalls.append(f"offer value {fmt_crore(offer_value)} < {fmt_crore(min_value)}")
        if min_pct is not None:
            required_parts.append(f"offer ≥ {fmt_pct(min_pct)}")
            if pct < min_pct:
                shortfalls.append(f"offer {fmt_pct(pct)} < {fmt_pct(min_pct)}")
        interpretive: list[str] = []
        if tier == 6:
            floor = self.spec.decimal("tier6_floor_pct")
            required_parts.append(f"offer ≥ {fmt_pct(floor)} (stricter reading)")
            if pct < floor and not shortfalls:
                interpretive.append(
                    f"offer {fmt_pct(pct)} meets the {fmt_pct(min_pct or Decimal(0))} condition "
                    f"but not the {fmt_pct(floor)} condition also cited for tier 6"
                )
        inputs.calc("Requirement: " + " and ".join(required_parts))

        review = []
        if tier >= 4:
            review.append(
                f"Tier {tier} thresholds are taken from secondary summaries of G.S.R. 184(E); "
                "confirm against the gazette text."
            )
        actual = (
            f"{fmt_pct(pct)} of {fmt_crore(market_cap)} = {fmt_crore(offer_value)} (tier {tier})"
        )
        if shortfalls:
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value=actual,
                gap="; ".join(shortfalls),
                explanation=f"The proposed public offer does not meet the tier {tier} minimum: "
                + "; ".join(shortfalls)
                + ".",
                remediation=[
                    "Increase the offer size (fresh issue and/or offer for sale) to meet the "
                    "tier minimum."
                ],
                review_reasons=review,
            )
        if interpretive:
            return self._result(
                Verdict.REQUIRES_HUMAN_REVIEW,
                inputs,
                actual_value=actual,
                explanation=(
                    "Tier 6 is ambiguous in the available sources: "
                    + "; ".join(interpretive)
                    + ". A reviewer must confirm which condition applies."
                ),
                review_reasons=review + interpretive,
            )
        return self._result(
            Verdict.PASS,
            inputs,
            actual_value=actual,
            explanation=f"The proposed public offer meets the tier {tier} minimum ("
            + " and ".join(required_parts)
            + ").",
            review_reasons=review,
        )
