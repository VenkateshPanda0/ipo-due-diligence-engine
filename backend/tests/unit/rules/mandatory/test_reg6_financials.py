"""
Tests for ICDR 2018 Reg 6(1)(a)-(c) financial rules (ruleset 2.0.0).

Expectations derive from the consolidated ICDR text (last amended 21-03-2026):
  6(1)(a) NTA >= ₹3 Cr in each of the preceding three full years (12 months each);
          monetary assets <= 50% of NTA, with the firm-commitment and OFS provisos.
  6(1)(b) average operating profit >= ₹15 Cr over the preceding three years, with
          operating profit in EACH of them.
  6(1)(c) net worth >= ₹1 Cr in each of the preceding three full years.
"""

from __future__ import annotations

import pytest

from app.models.enums import FieldStatus, ListingRoute, Verdict
from app.rules.mandatory.net_tangible_assets import MonetaryAssetsRule, NTARule
from app.rules.mandatory.net_worth import NetWorthRule
from app.rules.mandatory.profitability import ProfitabilityRule
from tests.fixtures.builders import D, base, ev, update, with_years


# --------------------------------------------------------------------- NTA_3CR
class TestNTA:
    rule = NTARule()

    def test_metadata_cites_icdr_2018_reg_6(self) -> None:
        assert "Regulation 6(1)(a)" in self.rule.spec.provision
        assert "26" not in self.rule.spec.provision

    @pytest.mark.parametrize(
        ("values", "verdict"),
        [
            (["3", "3", "3"], Verdict.PASS),  # exactly at threshold
            (["3.01", "40", "100"], Verdict.PASS),
            (["2.99", "40", "40"], Verdict.FAIL),  # oldest of the three fails
            (["40", "40", "2.999999"], Verdict.FAIL),
            (["-5", "40", "40"], Verdict.FAIL),  # negative NTA
        ],
    )
    def test_boundaries(self, values: list[str], verdict: Verdict) -> None:
        assert (
            self.rule.evaluate(with_years(base(), "net_tangible_assets", values)).verdict == verdict
        )

    def test_only_last_three_years_considered(self) -> None:
        c = with_years(base(), "net_tangible_assets", ["0.5", "0.5", "10", "10", "10"])
        assert self.rule.evaluate(c).verdict == Verdict.PASS

    def test_stub_period_is_skipped(self) -> None:
        # latest period is a 6-month stub with low NTA: excluded from "full years"
        c = with_years(
            base(), "net_tangible_assets", ["10", "10", "10", "10", "1"], months=[12, 12, 12, 12, 6]
        )
        assert self.rule.evaluate(c).verdict == Verdict.PASS

    def test_fewer_than_three_full_years_is_inconclusive(self) -> None:
        c = with_years(
            base(), "net_tangible_assets", ["10", "10", "10", "10", "10"], months=[6, 6, 6, 12, 12]
        )
        r = self.rule.evaluate(c)
        assert r.verdict == Verdict.INCONCLUSIVE
        assert r.missing_inputs

    def test_missing_value_is_inconclusive_not_fail(self) -> None:
        r = self.rule.evaluate(with_years(base(), "net_tangible_assets", [None, "10", "10"]))
        assert r.verdict == Verdict.INCONCLUSIVE
        assert any("net_tangible_assets" in m for m in r.missing_inputs)

    def test_low_confidence_value_requires_review(self) -> None:
        r = self.rule.evaluate(
            with_years(base(), "net_tangible_assets", [ev(D(10), low=True), "10", "10"])
        )
        assert r.verdict == Verdict.REQUIRES_HUMAN_REVIEW
        assert r.requires_human_review and r.review_reasons

    def test_confirmed_low_confidence_value_is_reliable(self) -> None:
        r = self.rule.evaluate(
            with_years(
                base(), "net_tangible_assets", [ev(D(10), low=True, confirmed=True), "10", "10"]
            )
        )
        assert r.verdict == Verdict.PASS

    def test_conflicting_candidates_require_review(self) -> None:
        r = self.rule.evaluate(
            with_years(
                base(),
                "net_tangible_assets",
                [ev(D(10), status=FieldStatus.CONFLICTING_CANDIDATES), "10", "10"],
            )
        )
        assert r.verdict == Verdict.REQUIRES_HUMAN_REVIEW

    def test_reliable_failure_wins_over_unreliable_other_year(self) -> None:
        r = self.rule.evaluate(
            with_years(base(), "net_tangible_assets", [ev(D(10), low=True), "1", "10"])
        )
        assert r.verdict == Verdict.FAIL

    def test_unreliable_failing_value_never_fails(self) -> None:
        r = self.rule.evaluate(
            with_years(base(), "net_tangible_assets", [ev(D(1), low=True), "10", "10"])
        )
        assert r.verdict == Verdict.REQUIRES_HUMAN_REVIEW

    def test_not_applicable_under_reg_6_2(self) -> None:
        c = update(base(), "issue_details", listing_route=ListingRoute.MAINBOARD_REG6_2)
        c = with_years(c, "net_tangible_assets", ["0", "0", "0"])
        r = self.rule.evaluate(c)
        assert r.verdict == Verdict.NOT_APPLICABLE and not r.applicable

    def test_result_carries_evidence_and_calculation(self) -> None:
        r = self.rule.evaluate(base())
        assert len(r.evidence) == 3
        assert all(e.page_number == 1 for e in r.evidence)
        assert len(r.calculation) == 3
        assert r.rule_version == "2.0.0"


# ------------------------------------------------------ MONETARY_ASSETS_50PCT
class TestMonetaryAssets:
    rule = MonetaryAssetsRule()

    @pytest.mark.parametrize(
        ("monetary", "nta", "verdict"),
        [
            ("5", "10", Verdict.PASS),  # exactly 50%
            ("5.0001", "10", Verdict.INCONCLUSIVE),  # breach; commitment unknown
            ("0", "10", Verdict.PASS),
        ],
    )
    def test_boundaries(self, monetary: str, nta: str, verdict: Verdict) -> None:
        c = with_years(base(), "monetary_assets", [monetary] * 3)
        c = with_years(c, "net_tangible_assets", [nta] * 3)
        assert self.rule.evaluate(c).verdict == verdict

    def test_breach_without_commitment_fails(self) -> None:
        c = with_years(base(), "monetary_assets", ["30", "5", "5"])
        c = update(c, "issue_details", excess_monetary_assets_committed=False)
        r = self.rule.evaluate(c)
        assert r.verdict == Verdict.FAIL and r.remediation

    def test_breach_with_firm_commitment_passes_with_review_note(self) -> None:
        c = with_years(base(), "monetary_assets", ["30", "5", "5"])
        c = update(c, "issue_details", excess_monetary_assets_committed=True)
        r = self.rule.evaluate(c)
        assert r.verdict == Verdict.PASS
        assert r.requires_human_review

    def test_offer_for_sale_only_is_exempt(self) -> None:
        c = with_years(base(), "monetary_assets", ["44", "44", "44"])
        c = update(c, "issue_details", issue_type="offer_for_sale")
        assert self.rule.evaluate(c).verdict == Verdict.NOT_APPLICABLE

    def test_mixed_issue_is_not_exempt(self) -> None:
        c = with_years(base(), "monetary_assets", ["44", "44", "44"])
        c = update(c, "issue_details", issue_type="mixed", excess_monetary_assets_committed=False)
        assert self.rule.evaluate(c).verdict == Verdict.FAIL

    def test_zero_nta_is_a_breach_not_a_crash(self) -> None:
        c = with_years(base(), "net_tangible_assets", ["0", "10", "10"])
        c = update(c, "issue_details", excess_monetary_assets_committed=False)
        assert self.rule.evaluate(c).verdict == Verdict.FAIL

    def test_missing_monetary_assets(self) -> None:
        assert (
            self.rule.evaluate(with_years(base(), "monetary_assets", [None, "1", "1"])).verdict
            == Verdict.INCONCLUSIVE
        )

    def test_calculated_ratio_marked_as_calculated(self) -> None:
        r = self.rule.evaluate(base())
        assert any(e.kind == "calculated" for e in r.evidence)


# ------------------------------------------------ AVG_OPERATING_PROFIT_15CR
class TestProfitability:
    rule = ProfitabilityRule()

    @pytest.mark.parametrize(
        ("values", "verdict"),
        [
            (["15", "15", "15"], Verdict.PASS),  # exactly at average
            (["5", "20", "20"], Verdict.PASS),  # avg 15 with profit each year
            (["14.99", "15", "15"], Verdict.FAIL),  # avg 14.9966..
            (["0", "30", "30"], Verdict.FAIL),  # avg 20 but no profit in one year
            (["-1", "40", "40"], Verdict.FAIL),
            (["0.01", "22.495", "22.495"], Verdict.PASS),  # avg exactly 15.00
        ],
    )
    def test_boundaries(self, values: list[str], verdict: Verdict) -> None:
        assert self.rule.evaluate(with_years(base(), "operating_profit", values)).verdict == verdict

    def test_v1_best_three_of_five_no_longer_applies(self) -> None:
        # Old rule took best 3 of 5 (would pass with two strong early years).
        c = with_years(base(), "operating_profit", ["50", "50", "5", "5", "5"])
        assert self.rule.evaluate(c).verdict == Verdict.FAIL

    def test_loss_year_failure_from_reliable_data_even_if_other_missing(self) -> None:
        r = self.rule.evaluate(with_years(base(), "operating_profit", [None, "-3", "20"]))
        assert r.verdict == Verdict.FAIL

    def test_missing_year_inconclusive(self) -> None:
        assert (
            self.rule.evaluate(with_years(base(), "operating_profit", [None, "30", "30"])).verdict
            == Verdict.INCONCLUSIVE
        )

    def test_average_is_exact_decimal(self) -> None:
        r = self.rule.evaluate(with_years(base(), "operating_profit", ["10", "15", "20.0000001"]))
        assert r.verdict == Verdict.PASS
        assert any("Average" in step for step in r.calculation)


# --------------------------------------------------------------- NET_WORTH_1CR
class TestNetWorth:
    rule = NetWorthRule()

    @pytest.mark.parametrize(
        ("values", "verdict"),
        [
            (["1", "1", "1"], Verdict.PASS),
            (["0.99", "50", "50"], Verdict.FAIL),
            (["-10", "50", "50"], Verdict.FAIL),
            (["50", "50", "50"], Verdict.PASS),
        ],
    )
    def test_boundaries(self, values: list[str], verdict: Verdict) -> None:
        assert self.rule.evaluate(with_years(base(), "net_worth", values)).verdict == verdict

    def test_gap_identifies_worst_year(self) -> None:
        r = self.rule.evaluate(with_years(base(), "net_worth", ["0.5", "0.2", "5"]))
        assert r.verdict == Verdict.FAIL and r.gap is not None and "FY2023" in r.gap

    def test_missing(self) -> None:
        assert (
            self.rule.evaluate(with_years(base(), "net_worth", ["5", None, "5"])).verdict
            == Verdict.INCONCLUSIVE
        )
