"""
backend/app/rules/mandatory/minimum_capital.py

Stock-exchange main-board listing criteria (thresholds UNVERIFIED — exchange
pages could not be retrieved; see the sources register):

  * MIN_POST_ISSUE_CAPITAL — post-issue paid-up capital ≥ ₹10 crore.
  * MIN_MARKET_CAP         — market capitalisation at issue price ≥ ₹25 crore.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.extracted_value import ExtractedValue
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs, fmt_crore


class _ThresholdRule(BaseRule):
    """Single-value minimum threshold rule."""

    _param: str
    _path: str
    _label: str
    _remediation: str

    @property
    def required_value(self) -> str:
        return f"{self._label} ≥ {fmt_crore(self.spec.decimal(self._param))}"

    def _value(self, company: CompanyData) -> ExtractedValue[Decimal] | None:
        raise NotImplementedError

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        threshold = self.spec.decimal(self._param)
        value = inputs.get(self._path, self._value(company))
        if value is None or inputs.unreliable:
            return self._undetermined(inputs)
        inputs.calc(f"{fmt_crore(value)} ≥ {fmt_crore(threshold)} → {value >= threshold}")
        if value >= threshold:
            return self._result(
                Verdict.PASS,
                inputs,
                actual_value=fmt_crore(value),
                explanation=(
                    f"{self._label} of {fmt_crore(value)} meets the exchange minimum of "
                    f"{fmt_crore(threshold)}."
                ),
            )
        return self._result(
            Verdict.FAIL,
            inputs,
            actual_value=fmt_crore(value),
            gap=f"{fmt_crore(threshold - value)} below threshold",
            explanation=(
                f"{self._label} of {fmt_crore(value)} is below the exchange minimum of "
                f"{fmt_crore(threshold)}."
            ),
            remediation=[self._remediation],
        )


class MinPostIssueCapitalRule(_ThresholdRule):
    rule_id = "MIN_POST_ISSUE_CAPITAL"
    _param = "min_post_issue_paid_up_crore"
    _path = "issue_details.post_issue_paid_up_capital"
    _label = "Post-issue paid-up capital"
    _remediation = (
        "Issuers below the main-board minimum may consider the SME route (ICDR Chapter IX, "
        "Reg 229), which this engine does not evaluate."
    )

    def _value(self, company: CompanyData) -> ExtractedValue[Decimal] | None:
        return company.issue_details.post_issue_paid_up_capital


class MinMarketCapRule(_ThresholdRule):
    rule_id = "MIN_MARKET_CAP"
    _param = "min_market_cap_crore"
    _path = "issue_details.expected_market_cap"
    _label = "Market capitalisation at issue price"
    _remediation = "Revisit issue pricing / capital structure with the lead managers."

    def _value(self, company: CompanyData) -> ExtractedValue[Decimal] | None:
        return company.issue_details.expected_market_cap
