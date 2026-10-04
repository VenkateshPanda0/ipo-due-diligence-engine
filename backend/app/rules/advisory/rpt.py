"""
backend/app/rules/advisory/rpt.py

RPT_DISCLOSURE — related party transaction diligence indicator. The 20 % of
revenue ratio is an engineering heuristic, not a LODR threshold.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs, fmt_crore, fmt_pct


class RPTDisclosureRule(BaseRule):
    """Arm's-length certification; high RPT concentration noted for review."""

    rule_id = "RPT_DISCLOSURE"

    @property
    def required_value(self) -> str:
        return "Related party transactions certified at arm's length"

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        rpt = company.rpt
        certified = inputs.get("rpt.arm_length_certified", rpt.arm_length_certified)
        total = inputs.get("rpt.total_rpt_value", rpt.total_rpt_value)
        if certified is False and inputs.is_reliable(rpt.arm_length_certified):
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value="Not certified at arm's length",
                gap="Arm's-length certification absent",
                explanation=(
                    "Related party transactions are not certified as being at arm's length."
                ),
                remediation=[
                    "Obtain audit-committee approval / arm's-length certification and disclose "
                    "fully."
                ],
            )
        if certified is None or total is None or inputs.unreliable:
            return self._undetermined(inputs)
        notes: list[str] = []
        fys = company.financials.fiscal_years
        if fys and total > 0:
            latest = fys[-1]
            revenue = inputs.get(f"financials.{latest.year_label}.revenue", latest.revenue)
            if revenue is not None and revenue > 0 and inputs.is_reliable(latest.revenue):
                ratio = total / revenue
                inputs.calc(
                    f"RPT / revenue = {fmt_crore(total)} / {fmt_crore(revenue)} = "
                    f"{fmt_pct(ratio * 100)}"
                )
                if ratio > self.spec.decimal("max_rpt_revenue_ratio"):
                    notes.append(
                        f"RPT value is {fmt_pct(ratio * Decimal(100))} of latest-year revenue "
                        "(above the 20% heuristic)."
                    )
        return self._result(
            Verdict.PASS,
            inputs,
            actual_value=(
                f"{fmt_crore(total)} across {len(rpt.transactions)} transaction(s), certified"
            ),
            explanation="Related party transactions are certified at arm's length."
            + (" " + " ".join(notes) if notes else ""),
            review_reasons=notes,
        )
