"""Decision engine: outcome precedence, progress counts, report metadata."""

from __future__ import annotations

from typing import ClassVar

import pytest

from app.engine.decision_engine import DecisionEngine, company_fingerprint
from app.engine.rules_engine import RulesEngine
from app.models.company_data import CompanyData
from app.models.enums import IPOStatus, ListingRoute, ScreeningOutcome, Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule
from app.rules.registry import RuleRegistry
from tests.fixtures.builders import D, base, declarations, ev, update, with_years


@pytest.fixture(scope="module")
def engine() -> DecisionEngine:
    return DecisionEngine(RuleRegistry())


def test_clean_company_has_no_failure_identified(engine: DecisionEngine) -> None:
    r = engine.evaluate(base())
    assert r.outcome == ScreeningOutcome.NO_FAILURE_IDENTIFIED
    assert r.status == IPOStatus.ELIGIBLE  # legacy compatibility
    assert r.ruleset_version.version == "2.0.0"
    assert r.engine_version and r.input_sha256 and r.limitations
    assert any("not a legal determination" in o for o in r.observations)
    assert not any("appears eligible" in o for o in r.observations)


def test_failure_dominates_review_and_missing(engine: DecisionEngine) -> None:
    c = with_years(base(), "net_worth", ["0.5", "5", "5"])
    c = with_years(c, "net_tangible_assets", [ev(D(10), low=True), "10", "10"])
    c = c.model_copy(update={"declarations": declarations(debarred_by_sebi=None)})
    r = engine.evaluate(c)
    assert r.outcome == ScreeningOutcome.SCREENING_FAILURE
    assert r.status == IPOStatus.NOT_ELIGIBLE


def test_review_dominates_missing(engine: DecisionEngine) -> None:
    c = with_years(base(), "net_tangible_assets", [ev(D(10), low=True), "10", "10"])
    c = c.model_copy(update={"declarations": declarations(debarred_by_sebi=None)})
    r = engine.evaluate(c)
    assert r.outcome == ScreeningOutcome.AWAITING_HUMAN_REVIEW
    assert r.status == IPOStatus.NEEDS_REVIEW


def test_missing_evidence_gives_insufficient_evidence(engine: DecisionEngine) -> None:
    c = base().model_copy(update={"declarations": declarations(debarred_by_sebi=None)})
    r = engine.evaluate(c)
    assert r.outcome == ScreeningOutcome.INSUFFICIENT_EVIDENCE
    assert any("ICDR_REG5" in i for i in r.unresolved_issues)


def test_advisory_failure_never_changes_outcome(engine: DecisionEngine) -> None:
    c = update(base(), "auditor", has_qualifications=ev(True))
    c = update(c, "litigation", has_criminal_cases=ev(True))
    r = engine.evaluate(c)
    assert r.outcome == ScreeningOutcome.NO_FAILURE_IDENTIFIED
    assert r.advisory_progress.failed == 2


def test_sme_route_is_unsupported_scope(engine: DecisionEngine) -> None:
    r = engine.evaluate(update(base(), "issue_details", listing_route=ListingRoute.SME_CHAPTER_IX))
    assert r.outcome == ScreeningOutcome.UNSUPPORTED_SCOPE
    assert r.status == IPOStatus.NEEDS_REVIEW
    assert all(x.verdict == Verdict.NOT_APPLICABLE for x in r.mandatory_results)


def test_reg6_2_route_replaces_reg6_1_financial_tests(engine: DecisionEngine) -> None:
    c = with_years(base(), "operating_profit", ["-5", "-5", "-5"])
    c = update(
        c,
        "issue_details",
        listing_route=ListingRoute.MAINBOARD_REG6_2,
        is_book_built=True,
        refund_undertaking=True,
        qib_net_offer_allocation=ev(D(75)),
    )
    r = engine.evaluate(c)
    assert r.outcome == ScreeningOutcome.NO_FAILURE_IDENTIFIED
    by_id = {x.rule_id: x.verdict for x in r.mandatory_results}
    assert by_id["AVG_OPERATING_PROFIT_15CR"] == Verdict.NOT_APPLICABLE
    assert by_id["ICDR_REG6_2_QIB_ROUTE"] == Verdict.PASS


def test_reg6_1_failure_suggests_reg6_2(engine: DecisionEngine) -> None:
    r = engine.evaluate(with_years(base(), "operating_profit", ["1", "1", "1"]))
    assert any("Reg 6(2)" in o for o in r.observations)


def test_progress_counts_sum(engine: DecisionEngine) -> None:
    r = engine.evaluate(base())
    p = r.mandatory_progress
    assert (
        p.passed + p.failed + p.inconclusive + p.requires_review + p.not_applicable == p.total_rules
    )
    assert p.not_applicable >= 2  # name change + Reg 6(2)


def test_pass_percentage_excludes_not_applicable(engine: DecisionEngine) -> None:
    assert engine.evaluate(base()).mandatory_progress.pass_percentage == D("100.00")


def test_determinism_except_ids_and_times(engine: DecisionEngine) -> None:
    a, b = engine.evaluate(base()), engine.evaluate(base())
    strip = {"report_id", "evaluated_at"}
    da = a.model_dump(mode="json", exclude=strip)
    db = b.model_dump(mode="json", exclude=strip)
    for d in (da, db):
        for grp in ("mandatory_results", "advisory_results"):
            for res in d[grp]:
                res.pop("evaluated_at")
    assert da == db
    assert a.input_sha256 == company_fingerprint(base())


def test_gap_items_for_fail_and_undetermined(engine: DecisionEngine) -> None:
    c = with_years(base(), "net_worth", ["0.5", "5", "5"])
    c = c.model_copy(update={"declarations": declarations(debarred_by_sebi=None)})
    gaps = {g.rule_id: g for g in engine.evaluate(c).gap_analysis}
    assert gaps["NET_WORTH_1CR"].verdict == "fail"
    assert gaps["ICDR_REG5_INELIGIBLE_ENTITIES"].verdict == "inconclusive"
    assert "not a regulatory failure" in gaps["ICDR_REG5_INELIGIBLE_ENTITIES"].earliest_eligible_fy
    assert all(g.professional_review_required for g in gaps.values())
    assert any("not a guarantee" in s for s in gaps["NET_WORTH_1CR"].remediation_steps)


class _Boom(BaseRule):
    rule_id: ClassVar[str] = "NTA_3CR"

    @property
    def required_value(self) -> str:
        return "x"

    def _evaluate(self, company: CompanyData) -> RuleResult:
        raise RuntimeError("secret internal path /etc/passwd")


def test_rule_exception_is_isolated_and_not_leaked() -> None:
    reg = RuleRegistry()
    reg._rules["NTA_3CR"] = _Boom(reg.ruleset.spec("NTA_3CR"))  # noqa: SLF001
    results = RulesEngine(reg).evaluate_all(base())
    boom = next(r for r in results if r.rule_id == "NTA_3CR")
    assert boom.verdict == Verdict.REQUIRES_HUMAN_REVIEW
    assert "/etc/passwd" not in boom.explanation and "RuntimeError" not in boom.explanation
    assert len(results) == len(reg)


def test_empty_company_never_fails() -> None:
    from app.models.company_data import CompanyIdentification

    r = DecisionEngine(RuleRegistry()).evaluate(
        CompanyData(identification=CompanyIdentification(company_name="X"))
    )
    assert r.outcome == ScreeningOutcome.INSUFFICIENT_EVIDENCE
    assert all(x.verdict != Verdict.FAIL for x in r.mandatory_results + r.advisory_results)


def test_fingerprint_ignores_legacy_ruleset_label() -> None:
    from datetime import date

    from app.engine.decision_engine import company_fingerprint
    from app.models.ruleset_version import RulesetVersion
    from tests.fixtures.company_data_factory import CompanyDataFactory

    company = CompanyDataFactory.create()
    relabelled = company.model_copy(
        update={
            "ruleset_version": RulesetVersion(
                version="9.9.9", effective_date=date(2000, 1, 1), description="x", regulations=[]
            )
        }
    )
    assert company_fingerprint(company) == company_fingerprint(relabelled)
