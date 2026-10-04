"""
backend/app/rules/advisory/auditor.py

AUDITOR_QUALIFICATION — flags qualifications or a modified audit opinion
(diligence indicator; not a statutory eligibility condition).
"""

from __future__ import annotations

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs


class AuditorQualificationRule(BaseRule):
    """No qualifications and no modified opinion."""

    rule_id = "AUDITOR_QUALIFICATION"

    @property
    def required_value(self) -> str:
        return "No qualifications and an unmodified audit opinion"

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        aud = company.auditor
        qual = inputs.get("auditor.has_qualifications", aud.has_qualifications)
        modified = inputs.get("auditor.has_modified_opinion", aud.has_modified_opinion)
        issues: list[str] = []
        if qual is True and inputs.is_reliable(aud.has_qualifications):
            issues.append("audit report contains qualifications")
        if modified is True and inputs.is_reliable(aud.has_modified_opinion):
            issues.append("auditor issued a modified opinion")
        name = aud.auditor_name or "statutory auditor"
        if issues:
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value=f"{name}: " + "; ".join(issues),
                gap="; ".join(issues),
                explanation=f"{name} reported: "
                + "; ".join(issues)
                + ". These require disclosure and diligence.",
                remediation=[
                    "Address the qualification / modification with the auditors before filing."
                ],
            )
        if inputs.missing or inputs.unreliable:
            return self._undetermined(inputs)
        return self._result(
            Verdict.PASS,
            inputs,
            actual_value=f"{name}: unmodified, no qualifications",
            explanation="No auditor qualification or modified opinion is evidenced.",
        )
