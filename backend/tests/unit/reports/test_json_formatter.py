from __future__ import annotations

import json

from app.engine.decision_engine import DecisionEngine
from app.reports.formatters.json_formatter import JSONReportFormatter
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


def test_json_formatter_outputs_parseable_report() -> None:
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    rendered = JSONReportFormatter().format(report)

    payload = json.loads(rendered)

    assert payload["report_id"] == str(report.report_id)
    assert payload["company_name"] == report.company_name
    assert payload["status"] == report.status.value
    assert payload["mandatory_progress"]["pass_percentage"] == "100.00"


def test_json_formatter_preserves_rule_results() -> None:
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create_not_eligible())
    payload = json.loads(JSONReportFormatter().format(report))

    assert payload["status"] == "not_eligible"
    assert len(payload["mandatory_results"]) == 13
    assert payload["gap_analysis"]
