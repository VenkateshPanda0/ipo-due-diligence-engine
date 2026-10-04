from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.db.base import Database
from app.db.repositories import SqlReportStorage
from app.engine.decision_engine import DecisionEngine
from app.models.ipo_report import IPOReport
from app.reports.storage import InMemoryReportStorage
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


def test_in_memory_storage_saves_and_retrieves_report() -> None:
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    storage = InMemoryReportStorage()

    storage.save(report.report_id, report)

    assert storage.exists(report.report_id)
    assert storage.get(report.report_id) == report


def test_in_memory_storage_returns_none_for_unknown_report() -> None:
    storage = InMemoryReportStorage()

    assert not storage.exists(uuid4())
    assert storage.get(uuid4()) is None


def test_in_memory_storage_allows_overwrite() -> None:
    first = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    second = DecisionEngine(RuleRegistry()).evaluate(
        CompanyDataFactory.create(company_name="Replacement Ltd")
    )
    storage = InMemoryReportStorage()

    storage.save(first.report_id, first)
    storage.save(first.report_id, second)

    assert storage.get(first.report_id) == second


def test_sqlite_storage_persists_report_across_instances(tmp_path) -> None:
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    database_url = f"sqlite:///{tmp_path / 'reports.db'}"

    db = Database(database_url)
    db.migrate()
    first_storage = SqlReportStorage(db)
    first_storage.save(report.report_id, report)
    second_storage = SqlReportStorage(Database(database_url))

    assert second_storage.exists(report.report_id)
    assert second_storage.get(report.report_id) == report


def test_sqlite_storage_round_trips_evidence(tmp_path) -> None:
    company = CompanyDataFactory.create()
    report = DecisionEngine(RuleRegistry()).evaluate(company)
    db = Database(f"sqlite:///{tmp_path / 'reports.db'}")
    db.migrate()
    storage = SqlReportStorage(db)
    storage.save(report.report_id, report)
    reloaded = storage.get(report.report_id)

    assert reloaded == report
    nta = next(r for r in reloaded.mandatory_results if r.rule_id == "NTA_3CR")
    expected = company.financials.fiscal_years[-3].net_tangible_assets
    assert expected is not None
    assert nta.evidence[0].value == str(expected.value)
    assert nta.evidence[0].page_number == expected.page_number


def test_reports_stored_under_ruleset_1_still_load() -> None:
    """Historical v1 reports must deserialise unchanged (no silent rewrite)."""
    sample = Path(__file__).resolve().parents[4] / "sample_data" / "reports" / "ruleset-1.0.0"
    for path in sorted(sample.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["ruleset_version"]["version"] != "1.0.0":
            continue
        report = IPOReport.model_validate(payload)
        assert report.outcome is None
        assert report.ruleset_version.version == "1.0.0"


def test_sql_reports_are_immutable(tmp_path) -> None:
    import pytest

    db = Database(f"sqlite:///{tmp_path / 'reports.db'}")
    db.migrate()
    storage = SqlReportStorage(db)
    report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())
    storage.save(report.report_id, report)
    with pytest.raises(ValueError, match="immutable"):
        storage.save(report.report_id, report)
