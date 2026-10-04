"""
backend/app/rules/mandatory/net_tangible_assets.py

SEBI ICDR 2018 Regulation 6(1)(a): net tangible assets and monetary assets.

NTA_3CR: NTA of at least ₹3 crore, restated and consolidated, in each of the
preceding three full (12-month) years.

MONETARY_ASSETS_50PCT: not more than 50 % of NTA held in monetary assets, with
two provisos — (i) excess utilised or firmly committed to be utilised in the
business; (ii) limit not applicable where the IPO is entirely an offer for sale.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.field_paths import fiscal_year_path
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule, Inputs, fmt_crore, fmt_pct, preceding_full_years


class NTARule(BaseRule):
    """Net tangible assets >= ₹3 crore in each of the preceding three full years."""

    rule_id = "NTA_3CR"

    @property
    def required_value(self) -> str:
        return (
            f"≥ {fmt_crore(self.spec.decimal('min_nta_crore'))} NTA in each of the "
            f"{self.spec.integer('years')} preceding full years"
        )

    def _evaluate(self, company: CompanyData) -> RuleResult:
        threshold = self.spec.decimal("min_nta_crore")
        years = self.spec.integer("years")
        inputs = Inputs()
        period = preceding_full_years(company, years)
        if len(period) < years:
            inputs.missing.append(
                f"financials.fiscal_years (need {years} full years, have {len(period)})"
            )
            return self._undetermined(inputs)

        summaries: list[str] = []
        reliable_failures: list[tuple[str, Decimal]] = []
        for fy in period:
            value = inputs.get(
                fiscal_year_path(fy.year_label, "net_tangible_assets"), fy.net_tangible_assets
            )
            if value is None:
                continue
            summaries.append(f"{fy.year_label}: {fmt_crore(value)}")
            ok = value >= threshold
            inputs.calc(f"{fy.year_label}: {fmt_crore(value)} ≥ {fmt_crore(threshold)} → {ok}")
            if not ok and inputs.is_reliable(fy.net_tangible_assets):
                reliable_failures.append((fy.year_label, value))
        actual = "; ".join(summaries) or None

        if reliable_failures:
            label, worst = min(reliable_failures, key=lambda t: t[1])
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value=actual,
                gap=f"{fmt_crore(threshold - worst)} below threshold in {label}",
                explanation=(
                    "Net tangible assets were below "
                    f"{fmt_crore(threshold)} in "
                    + ", ".join(lbl for lbl, _ in reliable_failures)
                    + "."
                ),
                remediation=[
                    "Reg 6(1)(a) is assessed on each of the preceding three full years; a "
                    "shortfall in a past year cannot be cured retrospectively.",
                    "Consider whether the issue can be structured under Reg 6(2) (book-built, "
                    "≥75% of net offer to QIBs) — requires professional advice.",
                ],
            )
        if inputs.missing or inputs.unreliable:
            return self._undetermined(inputs, actual)
        return self._result(
            Verdict.PASS,
            inputs,
            actual_value=actual,
            explanation=(
                f"NTA was at least {fmt_crore(threshold)} in each of "
                f"{', '.join(fy.year_label for fy in period)}."
            ),
        )


class MonetaryAssetsRule(BaseRule):
    """Monetary assets <= 50 % of NTA in each of the preceding three full years."""

    rule_id = "MONETARY_ASSETS_50PCT"

    @property
    def required_value(self) -> str:
        return (
            f"Monetary assets ≤ {fmt_pct(self.spec.decimal('max_monetary_pct'))} of NTA in each "
            "preceding full year (unless excess is committed, or the IPO is entirely an OFS)"
        )

    def _evaluate(self, company: CompanyData) -> RuleResult:
        limit = self.spec.decimal("max_monetary_pct")
        years = self.spec.integer("years")
        inputs = Inputs()
        issue = company.issue_details
        inputs.declared("issue_details.issue_type", issue.issue_type)
        if issue.issue_type == "offer_for_sale":
            inputs.calc("Issue type is entirely offer for sale → second proviso applies.")
            return self._result(
                Verdict.NOT_APPLICABLE,
                inputs,
                explanation=(
                    "The 50% monetary-asset limit does not apply where the IPO is made entirely "
                    "through an offer for sale (Reg 6(1)(a), second proviso)."
                ),
            )
        period = preceding_full_years(company, years)
        if len(period) < years:
            inputs.missing.append(
                f"financials.fiscal_years (need {years} full years, have {len(period)})"
            )
            return self._undetermined(inputs)

        breaches: list[tuple[str, Decimal]] = []
        summaries: list[str] = []
        all_reliable = True
        for fy in period:
            mon = inputs.get(fiscal_year_path(fy.year_label, "monetary_assets"), fy.monetary_assets)
            nta = inputs.get(
                fiscal_year_path(fy.year_label, "net_tangible_assets"), fy.net_tangible_assets
            )
            if mon is None or nta is None:
                continue
            reliable = inputs.is_reliable(fy.monetary_assets) and inputs.is_reliable(
                fy.net_tangible_assets
            )
            all_reliable = all_reliable and reliable
            if nta <= 0:
                inputs.calc(
                    f"{fy.year_label}: NTA {fmt_crore(nta)} ≤ 0 — ratio undefined; treated as "
                    "breach."
                )
                summaries.append(f"{fy.year_label}: NTA ≤ 0")
                if reliable:
                    breaches.append((fy.year_label, Decimal("Infinity")))
                continue
            pct = mon / nta * Decimal(100)
            inputs.calc(
                f"{fy.year_label}: {fmt_crore(mon)} / {fmt_crore(nta)} × 100 = {fmt_pct(pct)} "
                f"(limit {fmt_pct(limit)})"
            )
            inputs.calculated(
                fiscal_year_path(fy.year_label, "monetary_assets_pct_of_nta"),
                f"{pct:.4f}",
                "PERCENT",
            )
            summaries.append(f"{fy.year_label}: {fmt_pct(pct)}")
            if pct > limit and reliable:
                breaches.append((fy.year_label, pct))
        actual = "; ".join(summaries) or None

        if breaches:
            committed = inputs.require_flag(
                "issue_details.excess_monetary_assets_committed",
                issue.excess_monetary_assets_committed,
            )
            if committed is True:
                return self._result(
                    Verdict.PASS,
                    inputs,
                    actual_value=actual,
                    explanation=(
                        "Monetary assets exceeded 50% of NTA in "
                        + ", ".join(lbl for lbl, _ in breaches)
                        + ", but the issuer has utilised or made firm commitments to utilise the "
                        "excess (Reg 6(1)(a), first proviso)."
                    ),
                    review_reasons=["Reliance on the first proviso: verify the firm commitments."],
                )
            if committed is None:
                return self._result(
                    Verdict.INCONCLUSIVE,
                    inputs,
                    actual_value=actual,
                    explanation=(
                        "Monetary assets exceeded 50% of NTA in "
                        + ", ".join(lbl for lbl, _ in breaches)
                        + ". Whether the excess has been utilised or firmly committed (first "
                        "proviso) is not evidenced."
                    ),
                    remediation=[
                        "Provide evidence of utilisation or firm commitments for the excess."
                    ],
                )
            return self._result(
                Verdict.FAIL,
                inputs,
                actual_value=actual,
                gap="Monetary assets above 50% of NTA in " + ", ".join(lbl for lbl, _ in breaches),
                explanation=(
                    "Monetary assets exceeded 50% of NTA and the excess is not committed to "
                    "business use."
                ),
                remediation=[
                    "Utilise, or make firm commitments to utilise, excess monetary assets in the "
                    "business or project (first proviso).",
                    "A pure offer-for-sale IPO is exempt from the limit (second proviso).",
                ],
            )
        if inputs.missing or not all_reliable:
            return self._undetermined(inputs, actual)
        return self._result(
            Verdict.PASS,
            inputs,
            actual_value=actual,
            explanation="Monetary assets were within 50% of NTA in each preceding full year.",
        )
