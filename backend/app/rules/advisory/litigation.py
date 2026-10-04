"""
backend/app/rules/advisory/litigation.py

LITIGATION_RISK — diligence indicator. The 20 % of net worth ratio is an
engineering heuristic; ICDR materiality is set by the issuer's board policy.
"""

from __future__ import annotations

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs, fmt_crore, fmt_pct


class LitigationRiskRule(BaseRule):
    """Criminal cases or exposure above 20 % of latest net worth are flagged."""

    rule_id = "LITIGATION_RISK"

    @property
    def required_value(self) -> str:
        return "No pending criminal cases; total exposure ≤ 20% of latest net worth (heuristic)"

    def _evaluate(self, company: CompanyData) -> RuleResult:
        inputs = Inputs()
        lit = company.litigation
        criminal = inputs.get("litigation.has_criminal_cases", lit.has_criminal_cases)
        exposure = inputs.get("litigation.total_exposure", lit.total_exposure)
        issues: list[str] = []
        if criminal is True and inputs.is_reliable(lit.has_criminal_cases):
            issues.append("criminal case(s) pending against the company, promoters or directors")
        if exposure is not None and exposure > 0 and inputs.is_reliable(lit.total_exposure):
            fys = company.financials.fiscal_years
            if fys:
                latest = fys[-1]
                nw = inputs.get(f"financials.{latest.year_label}.net_worth", latest.net_worth)
                if nw is not None and nw > 0 and inputs.is_reliable(latest.net_worth):
                    ratio = exposure / nw
                    inputs.calc(
                        f"Exposure / net worth = {fmt_crore(exposure)} / {fmt_crore(nw)} = "
                        f"{fmt_pct(ratio * 100)}"
                    )
                    if ratio > self.spec.decimal("max_exposure_net_worth_ratio"):
                        issues.append(
                            f"exposure is {fmt_pct(ratio * 100)} of net worth (above the 20% "
                            "heuristic)"
                        )
        actual = (
            f"{len(lit.pending_cases)} case(s); exposure "
            f"{fmt_crore(exposure) if exposure is not None else 'unknown'}; criminal: {criminal}"
        )
        if issues:
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value=actual,
                gap="; ".join(issues),
                explanation="Litigation diligence flags: " + "; ".join(issues) + ".",
                remediation=[
                    "Ensure full disclosure under ICDR Schedule VI and assess with counsel."
                ],
            )
        if inputs.missing or inputs.unreliable:
            return self._undetermined(inputs, actual)
        return self._result(
            Verdict.PASS, inputs, actual_value=actual, explanation="No litigation flag raised."
        )
