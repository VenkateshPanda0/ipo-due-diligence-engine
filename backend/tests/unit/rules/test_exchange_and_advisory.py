"""Tests for exchange criteria (unverified thresholds) and advisory rules."""

from __future__ import annotations

import pytest

from app.models.enums import RuleCategory, Verdict
from app.rules.advisory.auditor import AuditorQualificationRule
from app.rules.advisory.governance import AuditCommitteeRule, BoardIndependenceRule
from app.rules.advisory.litigation import LitigationRiskRule
from app.rules.advisory.rpt import RPTDisclosureRule
from app.rules.mandatory.issue_size import IssueSizeRule
from app.rules.mandatory.minimum_capital import MinMarketCapRule, MinPostIssueCapitalRule
from app.rules.mandatory.track_record import TrackRecordRule
from tests.fixtures.builders import D, base, ev, update, with_years


@pytest.mark.parametrize(
    ("rule", "field", "threshold"),
    [
        (MinPostIssueCapitalRule(), "post_issue_paid_up_capital", "10"),
        (MinMarketCapRule(), "expected_market_cap", "25"),
        (IssueSizeRule(), "issue_size", "10"),
    ],
)
class TestExchangeThresholds:
    def test_at_threshold_passes(self, rule, field, threshold) -> None:  # type: ignore[no-untyped-def]
        assert (
            rule.evaluate(update(base(), "issue_details", **{field: ev(D(threshold))})).verdict
            == Verdict.PASS
        )

    def test_below_fails(self, rule, field, threshold) -> None:  # type: ignore[no-untyped-def]
        v = D(threshold) - D("0.01")
        assert (
            rule.evaluate(update(base(), "issue_details", **{field: ev(v)})).verdict == Verdict.FAIL
        )

    def test_missing_inconclusive(self, rule, field, threshold) -> None:  # type: ignore[no-untyped-def]
        assert (
            rule.evaluate(update(base(), "issue_details", **{field: None})).verdict
            == Verdict.INCONCLUSIVE
        )

    def test_marked_unverified(self, rule, field, threshold) -> None:  # type: ignore[no-untyped-def]
        assert rule.spec.verification_status.value == "unverified"
        assert rule.spec.legal_category.value == "exchange_listing_criterion"


def test_issue_size_5x_rule_removed() -> None:
    assert IssueSizeRule.rule_id == "EXCHANGE_MIN_ISSUE_SIZE"


class TestTrackRecord:
    rule = TrackRecordRule()

    def test_advisory(self) -> None:
        assert self.rule.category == RuleCategory.ADVISORY

    @pytest.mark.parametrize(
        ("years", "verdict"), [(3, Verdict.PASS), (2, Verdict.FAIL), (None, Verdict.INCONCLUSIVE)]
    )
    def test_years(self, years: int | None, verdict: Verdict) -> None:
        c = base().model_copy(
            update={
                "financials": base().financials.model_copy(update={"years_of_operation": years})
            }
        )
        assert self.rule.evaluate(c).verdict == verdict


class TestBoardIndependence:
    rule = BoardIndependenceRule()

    @pytest.mark.parametrize(
        ("total", "independent", "exec_chair", "promoter_chair", "verdict"),
        [
            (6, 2, False, False, Verdict.PASS),  # exactly 1/3
            (7, 2, False, False, Verdict.FAIL),  # 2/7 < 1/3
            (6, 3, True, False, Verdict.PASS),  # exactly 1/2
            (7, 3, True, False, Verdict.FAIL),  # 3/7 < 1/2
            (8, 3, False, True, Verdict.FAIL),  # promoter chair needs 1/2
            (8, 4, False, True, Verdict.PASS),
        ],
    )
    def test_matrix(
        self, total: int, independent: int, exec_chair: bool, promoter_chair: bool, verdict: Verdict
    ) -> None:
        c = update(
            base(),
            "governance",
            total_directors=ev(total),
            independent_directors=ev(independent),
            is_chair_executive=ev(exec_chair),
            is_chair_promoter=ev(promoter_chair),
        )
        assert self.rule.evaluate(c).verdict == verdict

    def test_cites_lodr_17_1_b(self) -> None:
        assert "17(1)(b)" in self.rule.spec.provision


class TestAuditCommittee:
    rule = AuditCommitteeRule()

    @pytest.mark.parametrize(
        ("total", "independent", "chair", "verdict"),
        [
            (3, 2, True, Verdict.PASS),  # exactly 2/3
            (4, 2, True, Verdict.FAIL),  # 1/2 < 2/3
            (2, 2, True, Verdict.FAIL),  # < 3 members
            (3, 3, False, Verdict.FAIL),  # chair not independent
        ],
    )
    def test_matrix(self, total: int, independent: int, chair: bool, verdict: Verdict) -> None:
        ac = base().governance.audit_committee.model_copy(
            update={
                "total_members": ev(total),
                "independent_members": ev(independent),
                "chair_is_independent": ev(chair),
            }
        )
        assert (
            self.rule.evaluate(update(base(), "governance", audit_committee=ac)).verdict == verdict
        )


class TestRPT:
    rule = RPTDisclosureRule()

    def test_not_certified_fails(self) -> None:
        assert (
            self.rule.evaluate(update(base(), "rpt", arm_length_certified=ev(False))).verdict
            == Verdict.FAIL
        )

    def test_high_volume_is_review_note_not_failure(self) -> None:
        r = self.rule.evaluate(update(base(), "rpt", total_rpt_value=ev(D(50))))
        assert r.verdict == Verdict.PASS and r.requires_human_review

    def test_heuristic_is_labelled(self) -> None:
        assert self.rule.spec.legal_category.value == "diligence_indicator"


class TestAuditor:
    rule = AuditorQualificationRule()

    def test_clean(self) -> None:
        assert self.rule.evaluate(base()).verdict == Verdict.PASS

    def test_qualified(self) -> None:
        assert (
            self.rule.evaluate(update(base(), "auditor", has_qualifications=ev(True))).verdict
            == Verdict.FAIL
        )

    def test_missing(self) -> None:
        assert (
            self.rule.evaluate(update(base(), "auditor", has_modified_opinion=None)).verdict
            == Verdict.INCONCLUSIVE
        )


class TestLitigation:
    rule = LitigationRiskRule()

    def test_criminal(self) -> None:
        assert (
            self.rule.evaluate(update(base(), "litigation", has_criminal_cases=ev(True))).verdict
            == Verdict.FAIL
        )

    def test_exposure_above_20pct_of_latest_net_worth(self) -> None:
        c = with_years(base(), "net_worth", ["50"])
        assert (
            self.rule.evaluate(update(c, "litigation", total_exposure=ev(D("10.01")))).verdict
            == Verdict.FAIL
        )
        assert (
            self.rule.evaluate(update(c, "litigation", total_exposure=ev(D("10")))).verdict
            == Verdict.PASS
        )
