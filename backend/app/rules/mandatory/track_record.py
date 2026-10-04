"""
backend/app/rules/mandatory/track_record.py

TRACK_RECORD_3Y — three-year operating track record (exchange criterion,
UNVERIFIED). Reclassified as ADVISORY in ruleset 2.0.0: ICDR Reg 6(1) already
requires three full years of restated financials, and the exchange text could
not be retrieved.
"""

from __future__ import annotations

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs


class TrackRecordRule(BaseRule):
    """Years of operation >= 3."""

    rule_id = "TRACK_RECORD_3Y"

    @property
    def required_value(self) -> str:
        return f"≥ {self.spec.integer('min_years')} years of operation"

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        minimum = self.spec.integer("min_years")
        years = company.financials.years_of_operation
        if years is None:
            inputs.missing.append("financials.years_of_operation")
            return self._undetermined(inputs)
        inputs.declared("financials.years_of_operation", str(years))
        inputs.calc(f"{years} ≥ {minimum} → {years >= minimum}")
        if years >= minimum:
            return self._result(
                Verdict.PASS,
                inputs,
                actual_value=f"{years} years",
                explanation=f"The company has {years} years of operation.",
            )
        return self._result(
            Verdict.FAIL,
            inputs,
            actual_value=f"{years} years",
            gap=f"{minimum - years} year(s) short",
            explanation=f"The company has {years} years of operation, below {minimum}.",
            remediation=[
                "Confirm the applicable exchange track-record criterion with the exchange."
            ],
        )
