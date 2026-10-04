"""
backend/app/rules/mandatory/profitability.py

SEBI ICDR 2018 Regulation 6(1)(b): average operating profit of at least ₹15
crore, restated and consolidated, during the preceding three years (of twelve
months each), with operating profit in each of these preceding three years.

Ruleset 1.0.0 used "best 3 of preceding 5 years" (the ICDR 2009 test); 2.0.0
uses the preceding three years only.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs, fmt_crore, preceding_full_years


class ProfitabilityRule(BaseRule):
    """Average operating profit >= ₹15 crore over the preceding three years, profit in each."""

    rule_id = "AVG_OPERATING_PROFIT_15CR"

    @property
    def required_value(self) -> str:
        return (
            "Average operating profit ≥ "
            f"{fmt_crore(self.spec.decimal('min_avg_operating_profit_crore'))} "
            f"over the preceding {self.spec.integer('years')} years, with operating profit in "
            "each year"
        )

    def _evaluate(self, company: CompanyData) -> RuleResult:
        threshold = self.spec.decimal("min_avg_operating_profit_crore")
        years = self.spec.integer("years")
        inputs = Inputs()
        period = preceding_full_years(company, years)
        if len(period) < years:
            inputs.missing.append(
                f"financials.fiscal_years (need {years} full years, have {len(period)})"
            )
            return self._undetermined(inputs)

        values: list[Decimal] = []
        loss_years: list[str] = []
        summaries: list[str] = []
        for fy in period:
            value = inputs.get(f"financials.{fy.year_label}.operating_profit", fy.operating_profit)
            if value is None:
                continue
            values.append(value)
            summaries.append(f"{fy.year_label}: {fmt_crore(value)}")
            if value <= 0 and inputs.is_reliable(fy.operating_profit):
                loss_years.append(fy.year_label)
        actual = "; ".join(summaries) or None

        if loss_years:
            inputs.calc("No operating profit in: " + ", ".join(loss_years))
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value=actual,
                gap="No operating profit in " + ", ".join(loss_years),
                explanation=(
                    "Reg 6(1)(b) requires operating profit in each of the preceding three years; "
                    "there was no operating profit in " + ", ".join(loss_years) + "."
                ),
                remediation=[
                    "The test is applied to the preceding three years; eligibility may change "
                    "once a further profitable full year is completed and restated.",
                    "Consider the Reg 6(2) route — requires professional advice.",
                ],
            )
        if inputs.missing or inputs.unreliable:
            return self._undetermined(inputs, actual)

        total = sum(values, Decimal(0))
        average = total / Decimal(len(values))
        inputs.calc(
            f"Average = ({' + '.join(str(v) for v in values)}) / {len(values)} = {average:.4f} Cr"
        )
        inputs.calculated("financials.average_operating_profit", f"{average:.4f}", "INR_CRORE")
        if average >= threshold:
            return self._result(
                Verdict.PASS,
                inputs,
                actual_value=f"Average {fmt_crore(average)} ({actual})",
                explanation=(
                    f"Average operating profit {fmt_crore(average)} meets {fmt_crore(threshold)}, "
                    "with operating profit in each year."
                ),
            )
        shortfall = threshold - average
        return self._result(
            Verdict.FAIL,
            inputs,
            actual_value=f"Average {fmt_crore(average)} ({actual})",
            gap=f"Average {fmt_crore(shortfall)} below threshold "
            f"(aggregate shortfall {fmt_crore(shortfall * years)} over {years} years)",
            explanation=(
                f"Average operating profit {fmt_crore(average)} is below {fmt_crore(threshold)}."
            ),
            remediation=[
                "Eligibility under Reg 6(1)(b) is re-tested on the latest three full years; "
                "increased operating profit in a future year can change the result.",
                "Consider the Reg 6(2) route — requires professional advice.",
            ],
        )
