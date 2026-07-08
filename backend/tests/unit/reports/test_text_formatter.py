from __future__ import annotations

from app.engine.decision_engine import DecisionEngine
from app.reports.formatters.text_formatter import TextReportFormatter
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


def test_text_formatter_contains_core_sections() -> None:
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create_not_eligible())
    rendered = TextReportFormatter().format(report)

    assert "IPO Due Diligence Report" in rendered
    assert "Mandatory Requirements" in rendered
    assert "Advisory Checks" in rendered
    assert "Gap Analysis" in rendered
    assert "Observations" in rendered
    assert "[FAIL]" in rendered


def test_text_formatter_renders_evidence_citations() -> None:
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    rendered = TextReportFormatter().format(report)

    assert "Evidence: Annual_Report_Test.pdf" in rendered
    assert "page(s) 1" in rendered
