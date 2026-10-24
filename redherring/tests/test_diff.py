from decimal import Decimal

from redherring.analyze import AnalysisReport, FactRecord, Summary
from redherring.diff import diff_reports
from redherring.flags.engine import Citation, Flag


def _fact(key: str, value: str, step: str = "10000", page: int = 1) -> FactRecord:
    return FactRecord(key=key, value=Decimal(value), step=Decimal(step), pdf_page=page, span="x")


def _report(facts: list[FactRecord], flags: list[Flag] | None = None) -> AnalysisReport:
    summary = Summary(
        doc_id="d", values_total=0, values_verified=0, footing_checked=0, footing_passed=0,
        consensus_groups=0, consensus_multi_source=0, consensus_unanimous_multi=0,
        values_without_period=0, values_without_unit=0, concepts={}, issue_facts_total=0,
        issue_facts_verified=0, values_ambiguous_dropped=0, flags=0, rules_decisive=0,
        rules_applicable=0,
    )  # fmt: skip
    return AnalysisReport(
        summary=summary, values=[], issue_facts=[], footing=[], consensus=[],
        facts=facts, flags=flags or [], rule_audit=[],
    )  # fmt: skip


def _flag(rule_id: str) -> Flag:
    return Flag(
        rule_id=rule_id, rule_name=rule_id, severity="medium", explanation="x", numbers={},
        citations=[Citation(pdf_page=1, span="x")], sources=[], heuristic=True,
    )  # fmt: skip


def test_a_changed_issue_size_is_reported_with_the_percentage() -> None:
    old = _report([_fact("issue.fresh_issue_amount", "7500000000")])
    new = _report([_fact("issue.fresh_issue_amount", "6500000000")])
    (c,) = diff_reports(old, new).changes
    assert c.kind == "changed"
    assert round(c.pct or 0, 1) == Decimal("-13.3")


def test_rounding_within_the_printed_precision_is_not_a_change() -> None:
    old = _report([_fact("financials.total_income.FY2025", "10507140000")])
    new = _report([_fact("financials.total_income.FY2025", "10507150000")])  # one step apart
    (c,) = diff_reports(old, new).changes
    assert c.kind == "same"


def test_a_restated_figure_beyond_the_precision_is_a_change() -> None:
    old = _report([_fact("financials.profit_after_tax.FY2025", "556480000")])
    new = _report([_fact("financials.profit_after_tax.FY2025", "601000000")])
    assert diff_reports(old, new).moved[0].kind == "changed"


def test_figures_present_in_only_one_version_are_added_or_removed() -> None:
    old = _report([_fact("objects.gcp_amount", "400000000")])
    new = _report([_fact("issue.total_issue_amount", "7000000000")])
    kinds = {c.key: c.kind for c in diff_reports(old, new).changes}
    assert kinds == {"objects.gcp_amount": "removed", "issue.total_issue_amount": "added"}


def test_flags_are_compared_by_rule() -> None:
    old = _report([], [_flag("A"), _flag("B")])
    new = _report([], [_flag("B"), _flag("C")])
    kinds = {f.rule_id: f.kind for f in diff_reports(old, new).flags}
    assert kinds == {"A": "removed", "B": "kept", "C": "added"}


def test_a_period_only_one_version_has_is_not_a_changed_figure() -> None:
    old = _report([_fact("financials.total_income.3M-2024-06-30", "2513010000")])
    new = _report([_fact("financials.total_income.6M-2024-09-30", "5053416000")])
    d = diff_reports(old, new)
    assert d.moved == [] and d.comparable == []
    assert {c.key for c in d.period_only} == {
        "financials.total_income.3M-2024-06-30",
        "financials.total_income.6M-2024-09-30",
    }
