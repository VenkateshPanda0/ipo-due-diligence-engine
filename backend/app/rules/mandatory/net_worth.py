"""
backend/app/rules/mandatory/net_worth.py

SEBI ICDR 2018 Regulation 6(1)(c): net worth of at least ₹1 crore in each of the
preceding three full years (of twelve months each), restated and consolidated.
Net worth as defined in Regulation 2(1)(hh).
"""

from __future__ import annotations

from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.field_paths import fiscal_year_path
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs, fmt_crore, preceding_full_years


class NetWorthRule(BaseRule):
    """Net worth >= ₹1 crore in each of the preceding three full years."""

    rule_id = "NET_WORTH_1CR"

    @property
    def required_value(self) -> str:
        return (
            f"≥ {fmt_crore(self.spec.decimal('min_net_worth_crore'))} net worth in each of the "
            f"{self.spec.integer('years')} preceding full years"
        )

    def _evaluate(self, company: CompanyData) -> RuleResult:
        threshold = self.spec.decimal("min_net_worth_crore")
        years = self.spec.integer("years")
        inputs = Inputs()
        period = preceding_full_years(company, years)
        if len(period) < years:
            inputs.missing.append(
                f"financials.fiscal_years (need {years} full years, have {len(period)})"
            )
            return self._undetermined(inputs)

        summaries: list[str] = []
        failures: list[tuple[str, Decimal]] = []
        for fy in period:
            value = inputs.get(fiscal_year_path(fy.year_label, "net_worth"), fy.net_worth)
            if value is None:
                continue
            summaries.append(f"{fy.year_label}: {fmt_crore(value)}")
            inputs.calc(
                f"{fy.year_label}: {fmt_crore(value)} ≥ {fmt_crore(threshold)} → "
                f"{value >= threshold}"
            )
            if value < threshold and inputs.is_reliable(fy.net_worth):
                failures.append((fy.year_label, value))
        actual = "; ".join(summaries) or None

        if failures:
            label, worst = min(failures, key=lambda t: t[1])
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value=actual,
                gap=f"{fmt_crore(threshold - worst)} below threshold in {label}",
                explanation=(
                    f"Net worth was below {fmt_crore(threshold)} in "
                    + ", ".join(lbl for lbl, _ in failures)
                    + "."
                ),
                remediation=[
                    "Each of the preceding three full years must meet the threshold; a past "
                    "shortfall cannot be cured retrospectively.",
                    "Consider the Reg 6(2) route — requires professional advice.",
                ],
            )
        if inputs.missing or inputs.unreliable:
            return self._undetermined(inputs, actual)
        return self._result(
            Verdict.PASS,
            inputs,
            actual_value=actual,
            explanation=(
                f"Net worth was at least {fmt_crore(threshold)} in each preceding full year."
            ),
        )
