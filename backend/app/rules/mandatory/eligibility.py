"""
backend/app/rules/mandatory/eligibility.py

SEBI ICDR 2018 statutory eligibility rules not tied to financial thresholds:

  * ICDR_REG5_INELIGIBLE_ENTITIES — Regulation 5(1)(a)-(d) and 5(2).
  * ICDR_REG6_1D_NAME_CHANGE      — Regulation 6(1)(d).
  * ICDR_REG6_2_QIB_ROUTE         — Regulation 6(2) alternative route.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs, fmt_pct

_REG5_CONDITIONS: tuple[tuple[str, str], ...] = (
    (
        "debarred_by_sebi",
        "issuer, promoter, promoter group, director or selling shareholder debarred by SEBI (Reg "
        "5(1)(a))",
    ),
    (
        "promoter_or_director_of_debarred_company",
        "promoter/director is a promoter/director of a debarred company (Reg 5(1)(b))",
    ),
    (
        "wilful_defaulter_or_fraudulent_borrower",
        "issuer, promoter or director is a wilful defaulter or fraudulent borrower (Reg 5(1)(c))",
    ),
    (
        "fugitive_economic_offender",
        "promoter or director is a fugitive economic offender (Reg 5(1)(d))",
    ),
    (
        "outstanding_convertibles_not_exempt",
        "outstanding convertible securities / rights to equity not covered by an exemption (Reg "
        "5(2))",
    ),
)


class IneligibleEntitiesRule(BaseRule):
    """ICDR Regulation 5: entities not eligible to make an IPO."""

    rule_id = "ICDR_REG5_INELIGIBLE_ENTITIES"

    @property
    def required_value(self) -> str:
        return "None of the Reg 5(1)(a)-(d) or Reg 5(2) disqualifications applies"

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        decl = company.declarations
        triggered: list[str] = []
        unreliable_true = False
        for attr, label in _REG5_CONDITIONS:
            ev = getattr(decl, attr)
            value = inputs.get(f"declarations.{attr}", ev)
            if value is True:
                if inputs.is_reliable(ev):
                    triggered.append(label)
                else:
                    unreliable_true = True
        if triggered:
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value="; ".join(triggered),
                gap="Disqualification applies: " + "; ".join(triggered),
                explanation="The issuer is not eligible to make an IPO while: "
                + "; ".join(triggered)
                + ".",
                remediation=[
                    "Disqualifications under Reg 5 are legal matters; obtain advice from "
                    "securities counsel. Expired debarments are excluded by the Explanation.",
                ],
            )
        if inputs.missing or inputs.unreliable or unreliable_true:
            return self._undetermined(inputs)
        return self._result(
            Verdict.PASS,
            inputs,
            actual_value="No disqualification declared",
            explanation="All Reg 5 conditions are evidenced as not applying.",
        )


class NameChangeRule(BaseRule):
    """ICDR Regulation 6(1)(d): revenue from the activity indicated by a new name."""

    rule_id = "ICDR_REG6_1D_NAME_CHANGE"

    @property
    def required_value(self) -> str:
        return (
            "If the name changed within the last year, ≥ "
            f"{fmt_pct(self.spec.decimal('min_revenue_pct'))} "
            "of the preceding full year's revenue from the new-name activity"
        )

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        decl = company.declarations
        changed = inputs.get(
            "declarations.name_changed_within_last_year", decl.name_changed_within_last_year
        )
        if changed is None or (
            changed and not inputs.is_reliable(decl.name_changed_within_last_year)
        ):
            return self._undetermined(inputs)
        if changed is False:
            if inputs.unreliable:
                return self._undetermined(inputs)
            return self._result(
                Verdict.NOT_APPLICABLE,
                inputs,
                explanation="The issuer has not changed its name within the last one year.",
            )
        threshold = self.spec.decimal("min_revenue_pct")
        pct = inputs.get(
            "declarations.revenue_pct_from_new_name_activity",
            decl.revenue_pct_from_new_name_activity,
        )
        if pct is None or inputs.unreliable:
            return self._undetermined(inputs)
        inputs.calc(f"{fmt_pct(pct)} ≥ {fmt_pct(threshold)} → {pct >= threshold}")
        if pct >= threshold:
            return self._result(
                Verdict.PASS,
                inputs,
                actual_value=fmt_pct(pct),
                explanation=(
                    "At least half of the preceding full year's revenue came from the "
                    "new-name activity."
                ),
            )
        return self._result(
            Verdict.FAIL,
            inputs,
            actual_value=fmt_pct(pct),
            gap=f"{fmt_pct(threshold - pct)} below threshold",
            explanation=(
                "Less than 50% of the preceding full year's revenue came from the "
                "activity indicated by the new name."
            ),
            remediation=[
                "Seek professional advice on timing of the issue relative to the name change."
            ],
        )


class QIBRouteRule(BaseRule):
    """ICDR Regulation 6(2): book building with ≥75 % of net offer to QIBs."""

    rule_id = "ICDR_REG6_2_QIB_ROUTE"

    @property
    def required_value(self) -> str:
        return (
            "Book-built issue; undertaking to allot ≥ "
            f"{fmt_pct(self.spec.decimal('min_qib_allocation_pct'))} of the net offer to QIBs "
            "and to refund the full subscription if it fails to do so"
        )

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        issue = company.issue_details
        minimum = self.spec.decimal("min_qib_allocation_pct")
        book_built = inputs.require_flag("issue_details.is_book_built", issue.is_book_built)
        refund = inputs.require_flag("issue_details.refund_undertaking", issue.refund_undertaking)
        qib = inputs.get("issue_details.qib_net_offer_allocation", issue.qib_net_offer_allocation)

        failures: list[str] = []
        if book_built is False:
            failures.append("issue is not made through book building")
        if refund is False:
            failures.append("no undertaking to refund if the QIB allotment condition fails")
        if qib is not None and inputs.is_reliable(issue.qib_net_offer_allocation):
            inputs.calc(f"QIB allocation {fmt_pct(qib)} ≥ {fmt_pct(minimum)} → {qib >= minimum}")
            if qib < minimum:
                failures.append(
                    f"QIB allocation {fmt_pct(qib)} is below {fmt_pct(minimum)} of the net offer"
                )
        if failures:
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value="; ".join(failures),
                gap="; ".join(failures),
                explanation="Reg 6(2) conditions not met: " + "; ".join(failures) + ".",
                remediation=[
                    "Restructure the offer (book building, ≥75% QIB allocation, refund "
                    "undertaking) with the lead managers."
                ],
            )
        if inputs.missing or inputs.unreliable:
            return self._undetermined(inputs)
        return self._result(
            Verdict.PASS,
            inputs,
            actual_value=(
                f"Book built; QIB allocation {fmt_pct(qib or Decimal(0))}; refund undertaking given"
            ),
            explanation=(
                "Reg 6(2) alternative-route conditions are satisfied on the evidence provided."
            ),
        )
