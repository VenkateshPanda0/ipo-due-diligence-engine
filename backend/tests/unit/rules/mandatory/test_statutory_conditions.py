"""
Tests for ICDR Reg 5, Reg 6(1)(d), Reg 6(2), Reg 14, Reg 16(1)(a) and the
SCRR Rule 19(2)(b) minimum public offer (2026 tiers).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.enums import ListingRoute, Verdict
from app.rules.mandatory.eligibility import IneligibleEntitiesRule, NameChangeRule, QIBRouteRule
from app.rules.mandatory.float_requirements import FloatRequirementsRule
from app.rules.mandatory.promoter import PromoterContributionRule, PromoterLockInRule
from tests.fixtures.builders import D, base, declarations, ev, update


# ---------------------------------------------------------------- Reg 5
class TestIneligibleEntities:
    rule = IneligibleEntitiesRule()

    def test_all_declared_false_passes(self) -> None:
        assert self.rule.evaluate(base()).verdict == Verdict.PASS

    @pytest.mark.parametrize(
        "attr",
        [
            "debarred_by_sebi",
            "promoter_or_director_of_debarred_company",
            "wilful_defaulter_or_fraudulent_borrower",
            "fugitive_economic_offender",
            "outstanding_convertibles_not_exempt",
        ],
    )
    def test_each_disqualification_fails(self, attr: str) -> None:
        c = base().model_copy(update={"declarations": declarations(**{attr: ev(True)})})
        r = self.rule.evaluate(c)
        assert r.verdict == Verdict.FAIL

    def test_unknown_condition_is_inconclusive(self) -> None:
        c = base().model_copy(
            update={"declarations": declarations(fugitive_economic_offender=None)}
        )
        r = self.rule.evaluate(c)
        assert r.verdict == Verdict.INCONCLUSIVE
        assert "declarations.fugitive_economic_offender" in r.missing_inputs

    def test_unreliable_true_does_not_fail(self) -> None:
        c = base().model_copy(
            update={"declarations": declarations(debarred_by_sebi=ev(True, low=True))}
        )
        assert self.rule.evaluate(c).verdict == Verdict.REQUIRES_HUMAN_REVIEW

    def test_reliable_true_fails_even_if_others_missing(self) -> None:
        c = base().model_copy(
            update={
                "declarations": declarations(
                    debarred_by_sebi=ev(True), fugitive_economic_offender=None
                )
            }
        )
        assert self.rule.evaluate(c).verdict == Verdict.FAIL


# ---------------------------------------------------------- Reg 6(1)(d)
class TestNameChange:
    rule = NameChangeRule()

    def test_no_name_change_not_applicable(self) -> None:
        assert self.rule.evaluate(base()).verdict == Verdict.NOT_APPLICABLE

    @pytest.mark.parametrize(
        ("pct", "verdict"), [("50", Verdict.PASS), ("49.99", Verdict.FAIL), ("100", Verdict.PASS)]
    )
    def test_threshold(self, pct: str, verdict: Verdict) -> None:
        d = declarations(
            name_changed_within_last_year=ev(True), revenue_pct_from_new_name_activity=ev(D(pct))
        )
        assert self.rule.evaluate(base().model_copy(update={"declarations": d})).verdict == verdict

    def test_changed_but_revenue_unknown(self) -> None:
        d = declarations(name_changed_within_last_year=ev(True))
        assert (
            self.rule.evaluate(base().model_copy(update={"declarations": d})).verdict
            == Verdict.INCONCLUSIVE
        )

    def test_unknown_name_change(self) -> None:
        d = declarations(name_changed_within_last_year=None)
        assert (
            self.rule.evaluate(base().model_copy(update={"declarations": d})).verdict
            == Verdict.INCONCLUSIVE
        )


# --------------------------------------------------------------- Reg 6(2)
class TestQIBRoute:
    rule = QIBRouteRule()

    def _c(self, **kw: object):  # type: ignore[no-untyped-def]
        return update(base(), "issue_details", listing_route=ListingRoute.MAINBOARD_REG6_2, **kw)

    def test_not_applicable_on_reg6_1(self) -> None:
        assert self.rule.evaluate(base()).verdict == Verdict.NOT_APPLICABLE

    def test_pass_at_75(self) -> None:
        c = self._c(is_book_built=True, refund_undertaking=True, qib_net_offer_allocation=ev(D(75)))
        assert self.rule.evaluate(c).verdict == Verdict.PASS

    def test_fail_below_75(self) -> None:
        c = self._c(
            is_book_built=True, refund_undertaking=True, qib_net_offer_allocation=ev(D("74.99"))
        )
        assert self.rule.evaluate(c).verdict == Verdict.FAIL

    def test_fail_fixed_price(self) -> None:
        c = self._c(
            is_book_built=False, refund_undertaking=True, qib_net_offer_allocation=ev(D(75))
        )
        assert self.rule.evaluate(c).verdict == Verdict.FAIL

    def test_fail_no_refund_undertaking(self) -> None:
        c = self._c(
            is_book_built=True, refund_undertaking=False, qib_net_offer_allocation=ev(D(80))
        )
        assert self.rule.evaluate(c).verdict == Verdict.FAIL

    def test_inconclusive_when_unknown(self) -> None:
        c = self._c(is_book_built=True, qib_net_offer_allocation=ev(D(80)))
        assert self.rule.evaluate(c).verdict == Verdict.INCONCLUSIVE


# ------------------------------------------------------------- Reg 14(1)
class TestPromoterContribution:
    rule = PromoterContributionRule()

    @pytest.mark.parametrize(
        ("holding", "verdict"),
        [("20", Verdict.PASS), ("19.99", Verdict.FAIL), ("75", Verdict.PASS)],
    )
    def test_threshold(self, holding: str, verdict: Verdict) -> None:
        c = update(base(), "promoter", post_issue_holding=ev(D(holding)))
        assert self.rule.evaluate(c).verdict == verdict

    def test_proviso_shortfall_met_by_eligible_investors(self) -> None:
        c = update(
            base(),
            "promoter",
            post_issue_holding=ev(D(12)),
            eligible_non_promoter_contribution=ev(D(8)),
        )
        r = self.rule.evaluate(c)
        assert r.verdict == Verdict.PASS and r.requires_human_review

    def test_proviso_capped_at_10_percent(self) -> None:
        c = update(
            base(),
            "promoter",
            post_issue_holding=ev(D("9.99")),
            eligible_non_promoter_contribution=ev(D(15)),
        )
        assert self.rule.evaluate(c).verdict == Verdict.FAIL

    def test_proviso_exactly_10(self) -> None:
        c = update(
            base(),
            "promoter",
            post_issue_holding=ev(D(10)),
            eligible_non_promoter_contribution=ev(D(12)),
        )
        assert self.rule.evaluate(c).verdict == Verdict.PASS

    def test_no_identifiable_promoter(self) -> None:
        c = update(base(), "promoter", has_identifiable_promoter=False, post_issue_holding=None)
        assert self.rule.evaluate(c).verdict == Verdict.NOT_APPLICABLE

    def test_missing_holding(self) -> None:
        assert (
            self.rule.evaluate(update(base(), "promoter", post_issue_holding=None)).verdict
            == Verdict.INCONCLUSIVE
        )


# ---------------------------------------------------------- Reg 16(1)(a)
class TestLockIn:
    rule = PromoterLockInRule()

    @pytest.mark.parametrize(
        ("months", "capex", "verdict"),
        [
            (18, False, Verdict.PASS),
            (17, False, Verdict.FAIL),
            (36, True, Verdict.PASS),
            (35, True, Verdict.FAIL),
            (18, True, Verdict.FAIL),
            (36, None, Verdict.PASS),  # satisfies either requirement
            (18, None, Verdict.INCONCLUSIVE),
        ],
    )
    def test_matrix(self, months: int, capex: bool | None, verdict: Verdict) -> None:
        c = update(base(), "promoter", lock_in_months=ev(months), is_capex_issue=capex)
        assert self.rule.evaluate(c).verdict == verdict

    def test_effective_date_is_2021_amendment(self) -> None:
        assert str(self.rule.spec.effective_from) == "2021-08-13"


# ------------------------------------------------- SCRR Rule 19(2)(b) 2026
class TestPublicOffer:
    rule = FloatRequirementsRule()

    def _c(self, mcap: str, pct: str):  # type: ignore[no-untyped-def]
        return update(
            base(),
            "issue_details",
            expected_market_cap=ev(D(mcap)),
            public_offer_percentage=ev(D(pct)),
        )

    @pytest.mark.parametrize(
        ("mcap", "pct", "verdict", "tier"),
        [
            ("1600", "25", Verdict.PASS, 1),  # upper bound inclusive in tier 1
            ("1600", "24.99", Verdict.FAIL, 1),
            ("1600.01", "25", Verdict.PASS, 2),  # 400.0025 Cr offered
            ("4000", "10", Verdict.PASS, 2),  # exactly 400 Cr
            ("4000", "9.99", Verdict.FAIL, 2),
            ("4000.01", "10", Verdict.PASS, 3),
            ("50000", "9.99", Verdict.FAIL, 3),
            ("50001", "8", Verdict.PASS, 4),  # 4,000 Cr >= 1,000 and 8%
            ("60000", "7.99", Verdict.FAIL, 4),
            ("100000", "1", Verdict.FAIL, 4),  # 1,000 Cr but < 8%
            ("200000", "3.125", Verdict.PASS, 5),  # 6,250 Cr and >= 2.75%
            ("200000", "3", Verdict.FAIL, 5),  # 6,000 Cr < 6,250
            ("500000.01", "3", Verdict.PASS, 6),  # 15,000 Cr and >= 2.5%
            ("1000000", "1.6", Verdict.FAIL, 6),  # 16,000 Cr but < 2.5% floor
        ],
    )
    def test_tiers(self, mcap: str, pct: str, verdict: Verdict, tier: int) -> None:
        r = self.rule.evaluate(self._c(mcap, pct))
        assert r.verdict == verdict
        assert any(f"Tier {tier}" in step for step in r.calculation)

    def test_large_tiers_flag_review(self) -> None:
        assert self.rule.evaluate(self._c("200000", "5")).requires_human_review
        assert not self.rule.evaluate(self._c("800", "25")).requires_human_review

    def test_tier_lookup_function(self) -> None:
        assert self.rule.tier_requirements(Decimal("1600")) == (1, None, Decimal("25"))
        assert self.rule.tier_requirements(Decimal("1601"))[0] == 2

    def test_secondary_source_status(self) -> None:
        assert self.rule.spec.verification_status.value == "secondary_sources_only"

    def test_nonpositive_market_cap_needs_review(self) -> None:
        assert self.rule.evaluate(self._c("0", "25")).verdict == Verdict.REQUIRES_HUMAN_REVIEW

    def test_missing(self) -> None:
        c = update(base(), "issue_details", public_offer_percentage=None)
        assert self.rule.evaluate(c).verdict == Verdict.INCONCLUSIVE
