from datetime import UTC, date, datetime
from decimal import Decimal

from redherring.analyze import AnalysisReport, FactRecord, Summary
from redherring.flags.engine import Citation, Flag, RuleAudit
from redherring.flags.spec import Source
from redherring.ingest.manifest import DocType, ManifestEntry, Platform
from redherring.report_html import DISCLAIMER, indian, report_html


def _entry(issuer: str = "Demo Ltd") -> ManifestEntry:
    return ManifestEntry(
        doc_id="demo",
        url="https://example.invalid/demo.pdf",
        issuer=issuer,
        doc_type=DocType.RHP,
        platform=Platform.MAINBOARD,
        filing_date=date(2026, 1, 5),
        sha256="ab" * 32,
        size_bytes=1,
        fetched_at=datetime.now(UTC),
        local_path="raw/demo.pdf",
        content_type="application/pdf",
    )


def _summary(**kw: int) -> Summary:
    base = dict(
        doc_id="demo", values_total=10, values_verified=10, footing_checked=4, footing_passed=4,
        consensus_groups=5, consensus_multi_source=4, consensus_unanimous_multi=3,
        values_without_period=0, values_without_unit=0, concepts={}, issue_facts_total=0,
        issue_facts_verified=0, values_ambiguous_dropped=0, flags=0, rules_decisive=1,
        rules_applicable=5,
    )  # fmt: skip
    return Summary(**{**base, **kw})


def _flag(span: str = "General corporate purposes | 300") -> Flag:
    return Flag(
        rule_id="T",
        rule_name="Test rule",
        severity="high",
        explanation="30% against a limit of 25%.",
        numbers={},
        citations=[Citation(pdf_page=12, span=span)],
        sources=[
            Source(
                kind="regulation", ref="ICDR 2018", clause="Reg 7(2)", checked_on=date(2026, 10, 24)
            )
        ],
        heuristic=False,
    )


def _report(**kw: object) -> AnalysisReport:
    base: dict[str, object] = dict(
        summary=_summary(), values=[], issue_facts=[], footing=[], consensus=[],
        facts=[], flags=[], rule_audit=[],
    )  # fmt: skip
    return AnalysisReport(**{**base, **kw})


def test_indian_digit_grouping() -> None:
    assert indian(Decimal("12345678.5")) == "1,23,45,678.50"
    assert indian(Decimal("999.999")) == "1,000.00"
    assert indian(Decimal("-1234.5")) == "-1,234.50"
    assert indian(Decimal("0")) == "0.00"


def test_page_carries_the_disclaimer_and_links_every_citation_to_its_pdf_page() -> None:
    html = report_html(_report(flags=[_flag()]), _entry())
    assert DISCLAIMER in html
    assert 'href="https://example.invalid/demo.pdf#page=12"' in html
    assert "Reg 7(2)" in html
    assert "regulatory threshold" in html


def test_text_from_the_document_cannot_inject_markup() -> None:
    hostile = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    html = report_html(_report(flags=[_flag(span=hostile)]), _entry(issuer=hostile))
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html


def test_no_flags_is_not_presented_as_a_clean_bill() -> None:
    html = report_html(_report(), _entry())
    assert "not</strong> a clean bill of health" in html
    assert "1 of 5 applicable rules" in html


def test_annual_figures_are_shown_in_crore_with_page_links() -> None:
    facts = [
        FactRecord(
            key="financials.total_income.FY2026",
            value=Decimal("18507930000"),
            step=Decimal("10000"),
            pdf_page=76,
            span="Total Income | 18,507.93",
        )
    ]
    html = report_html(_report(facts=facts), _entry())
    assert "FY2026" in html
    assert "1,850.79" in html  # 18,507.93 million = 1,850.79 crore
    assert "#page=76" in html


def test_audit_states_why_a_rule_did_not_decide() -> None:
    audit = [
        RuleAudit(rule_id="R1", status="missing_inputs", missing=["objects.gcp_amount"]),
        RuleAudit(
            rule_id="R2", status="not_applicable", detail="not applied to this sector: lender"
        ),
    ]
    html = report_html(_report(rule_audit=audit), _entry())
    assert "objects.gcp_amount" in html
    assert "lender" in html


def test_rules_that_never_applied_are_collapsed_not_listed_as_gaps() -> None:
    audit = [
        RuleAudit(rule_id="R-LIVE", status="clear"),
        RuleAudit(rule_id="R-SME", status="other_platform"),
        RuleAudit(rule_id="R-OLD", status="not_in_force"),
    ]
    html = report_html(_report(rule_audit=audit), _entry())
    assert "2 rules set aside" in html
    head, _, aside = html.partition("rules set aside")
    assert "R-LIVE" in head and "R-SME" not in head
    assert "R-SME" in aside and "R-OLD" in aside
