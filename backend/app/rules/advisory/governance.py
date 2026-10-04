"""
backend/app/rules/advisory/governance.py

Post-listing governance obligations screened as listing-readiness indicators:

  * BOARD_INDEPENDENCE — SEBI LODR Regulation 17(1)(b).
  * AUDIT_COMMITTEE    — SEBI LODR Regulation 18(1)(a), (b), (d).

Advisory: results never affect the case outcome.
"""

from __future__ import annotations

from fractions import Fraction

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs


class BoardIndependenceRule(BaseRule):
    """Independent directors >= 1/3 (non-executive, non-promoter chair) or >= 1/2."""

    rule_id = "BOARD_INDEPENDENCE"

    @property
    def required_value(self) -> str:
        return (
            "≥ 1/3 independent directors if the chair is non-executive and not a promoter; "
            "otherwise ≥ 1/2"
        )

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        gov = company.governance
        total = inputs.get("governance.total_directors", gov.total_directors)
        independent = inputs.get("governance.independent_directors", gov.independent_directors)
        exec_chair = inputs.get("governance.is_chair_executive", gov.is_chair_executive)
        promoter_chair = inputs.get("governance.is_chair_promoter", gov.is_chair_promoter)
        if None in (total, independent, exec_chair, promoter_chair) or inputs.unreliable:
            return self._undetermined(inputs)
        assert total is not None and independent is not None
        if total <= 0:
            return self._result(
                Verdict.REQUIRES_HUMAN_REVIEW,
                inputs,
                explanation=f"Board size {total} is not valid.",
                review_reasons=["Implausible board size."],
            )
        half_required = bool(exec_chair) or bool(promoter_chair)
        required = self.spec.fraction(
            "min_fraction_other" if half_required else "min_fraction_non_exec_chair"
        )
        actual = Fraction(independent, total)
        inputs.calc(
            f"{independent}/{total} independent vs required {required} "
            f"(chair executive: {exec_chair}, chair promoter: {promoter_chair})"
        )
        actual_text = f"{independent} of {total} independent"
        if actual >= required:
            return self._result(
                Verdict.PASS,
                inputs,
                actual_value=actual_text,
                explanation=(
                    f"{actual_text}; meets the {required} requirement under LODR Reg 17(1)(b)."
                ),
            )
        needed = -(-required.numerator * total // required.denominator)  # ceil
        return self._result(
            Verdict.FAIL,
            inputs,
            actual_value=actual_text,
            gap=f"{needed - independent} more independent director(s) needed",
            explanation=(
                f"{actual_text}; LODR Reg 17(1)(b) requires at least {required} of the board."
            ),
            remediation=[
                f"Appoint at least {needed - independent} additional independent director(s) "
                "before listing."
            ],
        )


class AuditCommitteeRule(BaseRule):
    """Audit committee: >= 3 members, >= 2/3 independent, independent chair."""

    rule_id = "AUDIT_COMMITTEE"

    @property
    def required_value(self) -> str:
        return "≥ 3 members, ≥ 2/3 independent directors, independent chairperson"

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        ac = company.governance.audit_committee
        total = inputs.get("governance.audit_committee.total_members", ac.total_members)
        independent = inputs.get(
            "governance.audit_committee.independent_members", ac.independent_members
        )
        chair = inputs.get(
            "governance.audit_committee.chair_is_independent", ac.chair_is_independent
        )
        if None in (total, independent, chair) or inputs.unreliable:
            return self._undetermined(inputs)
        assert total is not None and independent is not None
        minimum = self.spec.integer("min_members")
        fraction = self.spec.fraction("min_independent_fraction")
        issues: list[str] = []
        if total < minimum:
            issues.append(f"{total} member(s); minimum is {minimum}")
        if total > 0 and Fraction(independent, total) < fraction:
            issues.append(f"{independent} of {total} independent; at least {fraction} required")
        if not chair:
            issues.append("chairperson is not an independent director")
        inputs.calc(f"members={total}, independent={independent}, chair independent={chair}")
        actual = f"{total} members, {independent} independent, chair independent: {chair}"
        if issues:
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value=actual,
                gap="; ".join(issues),
                explanation="Audit committee does not meet LODR Reg 18(1): "
                + "; ".join(issues)
                + ".",
                remediation=["Reconstitute the audit committee before listing."],
            )
        return self._result(
            Verdict.PASS,
            inputs,
            actual_value=actual,
            explanation="Audit committee composition meets LODR Reg 18(1)(a), (b) and (d).",
        )
