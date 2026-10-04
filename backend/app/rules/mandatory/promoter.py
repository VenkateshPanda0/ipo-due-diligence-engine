"""
backend/app/rules/mandatory/promoter.py

SEBI ICDR 2018 promoter rules:

  * PROMOTER_CONTRIBUTION_20 — Regulation 14(1) and provisos.
  * PROMOTER_LOCK_IN         — Regulation 16(1)(a) and proviso (w.e.f. 13-08-2021).
"""

from __future__ import annotations

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs, fmt_pct


class PromoterContributionRule(BaseRule):
    """Promoters hold at least 20 % of post-issue capital (Reg 14(1))."""

    rule_id = "PROMOTER_CONTRIBUTION_20"

    @property
    def required_value(self) -> str:
        return (
            f"Promoters hold ≥ {fmt_pct(self.spec.decimal('min_contribution_pct'))} of post-issue "
            "capital (shortfall up to "
            f"{fmt_pct(self.spec.decimal('max_non_promoter_shortfall_pct'))} "
            "may be met by eligible investors)"
        )

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        promoter = company.promoter
        minimum = self.spec.decimal("min_contribution_pct")
        cap = self.spec.decimal("max_non_promoter_shortfall_pct")
        if not promoter.has_identifiable_promoter:
            inputs.declared("promoter.has_identifiable_promoter", "false")
            return self._result(
                Verdict.NOT_APPLICABLE,
                inputs,
                explanation="The issuer has no identifiable promoter (Reg 14(1), second proviso).",
            )
        holding = inputs.get("promoter.post_issue_holding", promoter.post_issue_holding)
        if holding is None or inputs.unreliable:
            return self._undetermined(inputs)
        inputs.calc(f"Post-issue promoter holding {fmt_pct(holding)} vs minimum {fmt_pct(minimum)}")
        if holding >= minimum:
            return self._result(
                Verdict.PASS,
                inputs,
                actual_value=fmt_pct(holding),
                explanation=f"Promoters hold {fmt_pct(holding)} of post-issue capital.",
            )
        shortfall = minimum - holding
        others = inputs.get(
            "promoter.eligible_non_promoter_contribution",
            promoter.eligible_non_promoter_contribution,
        )
        if others is not None and inputs.unreliable:
            return self._undetermined(inputs, fmt_pct(holding))
        if others is not None:
            counted = min(others, cap)
            inputs.calc(
                f"First proviso: eligible non-promoter contribution {fmt_pct(others)} "
                f"(counted up to {fmt_pct(cap)}) → {fmt_pct(counted)}; total "
                f"{fmt_pct(holding + counted)}"
            )
            if holding + counted >= minimum:
                return self._result(
                    Verdict.PASS,
                    inputs,
                    actual_value=f"{fmt_pct(holding)} + {fmt_pct(counted)} (Reg 14(1) proviso)",
                    explanation=(
                        "The promoter shortfall is met by contributions from entities permitted by "
                        "the first proviso to Reg 14(1), within the 10% cap."
                    ),
                    review_reasons=[
                        "Verify that contributing entities qualify under the Reg 14(1) proviso."
                    ],
                )
        return self._result(
            Verdict.FAIL,
            inputs,
            actual_value=fmt_pct(holding),
            gap=f"{fmt_pct(shortfall)} of post-issue capital",
            explanation=(
                f"Promoters hold {fmt_pct(holding)} of post-issue capital, below "
                f"{fmt_pct(minimum)}, "
                "and the shortfall is not met under the Reg 14(1) proviso."
            ),
            remediation=[
                "Increase promoter holding, reduce the offer size, or arrange contributions from "
                "AIFs, FVCIs, scheduled commercial banks, PFIs, IRDAI-registered insurers, ≥5% "
                "non-individual public shareholders or promoter-group entities (max 10%).",
            ],
        )


class PromoterLockInRule(BaseRule):
    """Lock-in of minimum promoters' contribution (Reg 16(1)(a))."""

    rule_id = "PROMOTER_LOCK_IN"

    @property
    def required_value(self) -> str:
        return (
            f"Minimum promoters' contribution locked in for {self.spec.integer('standard_months')} "
            f"months ({self.spec.integer('capex_months')} months if the majority of fresh-issue "
            "proceeds is for capital expenditure)"
        )

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        promoter = company.promoter
        standard = self.spec.integer("standard_months")
        capex = self.spec.integer("capex_months")
        if not promoter.has_identifiable_promoter:
            inputs.declared("promoter.has_identifiable_promoter", "false")
            return self._result(
                Verdict.NOT_APPLICABLE,
                inputs,
                explanation=(
                    "No identifiable promoter, so there is no minimum promoters' "
                    "contribution to lock in."
                ),
            )
        months = inputs.get("promoter.lock_in_months", promoter.lock_in_months)
        is_capex = inputs.require_flag("promoter.is_capex_issue", promoter.is_capex_issue)
        if months is None or inputs.unreliable:
            return self._undetermined(inputs)
        if is_capex is None:
            if months >= capex:
                # satisfied whichever lock-in applies
                inputs.missing.clear()
                inputs.calc(
                    f"{months} months ≥ {capex} (stricter capex period) → satisfied in either case"
                )
                return self._result(
                    Verdict.PASS,
                    inputs,
                    actual_value=f"{months} months",
                    explanation=(
                        "The committed lock-in satisfies even the capital-expenditure lock-in."
                    ),
                )
            return self._undetermined(inputs, f"{months} months")
        required = capex if is_capex else standard
        inputs.calc(
            f"Required {required} months (capex issue: {is_capex}); committed {months} months"
        )
        if months >= required:
            return self._result(
                Verdict.PASS,
                inputs,
                actual_value=f"{months} months",
                explanation=(
                    f"Committed lock-in of {months} months meets the {required}-month requirement."
                ),
            )
        return self._result(
            Verdict.FAIL,
            inputs,
            actual_value=f"{months} months",
            gap=f"{required - months} months short",
            explanation=(
                f"Committed lock-in of {months} months is shorter than the required "
                f"{required} months."
            ),
            remediation=[f"Extend the promoter lock-in undertaking to at least {required} months."],
        )
