from __future__ import annotations

from app.engine.decision_engine import DecisionEngine
from app.reports.formatters.html_formatter import HTMLReportFormatter
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


def test_html_formatter_renders_complete_html_document() -> None:
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    rendered = HTMLReportFormatter().format(report)

    assert rendered.startswith("<!doctype html>")
    assert report.company_name in rendered
    assert "Mandatory Requirements" in rendered
    assert "Advisory Checks" in rendered
    assert "Annual_Report_Test.pdf" in rendered
    assert "{{" not in rendered


def test_html_formatter_escapes_untrusted_report_content() -> None:
    company = CompanyDataFactory.create(company_name="<script>alert('x')</script>")
    report = DecisionEngine(RuleRegistry()).evaluate(company)
    rendered = HTMLReportFormatter().format(report)

    assert "<script>alert" not in rendered
    assert "&lt;script&gt;" in rendered
