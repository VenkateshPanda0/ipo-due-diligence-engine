from __future__ import annotations

import pytest

from app.engine.decision_engine import DecisionEngine
from app.reports.report_generator import ReportGenerator
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


def test_report_generator_dispatches_all_formats() -> None:
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    generator = ReportGenerator()

    assert generator.get_available_formats() == ["html", "json", "text"]
    assert generator.generate(report, "json").startswith("{")
    assert generator.generate(report, "text").startswith("IPO Due Diligence Report")
    assert generator.generate(report, "html").startswith("<!doctype html>")


def test_report_generator_rejects_unknown_format() -> None:
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())

    with pytest.raises(ValueError, match="Unsupported report format"):
        ReportGenerator().generate(report, "pdf")
