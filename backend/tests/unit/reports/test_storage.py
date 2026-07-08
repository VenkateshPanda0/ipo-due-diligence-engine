from __future__ import annotations

from uuid import uuid4

from app.engine.decision_engine import DecisionEngine
from app.engine.evidence_mapper import EvidenceMapper
from app.models.rule_result import RuleResult
from app.reports.storage import InMemoryReportStorage, SQLiteReportStorage
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

    first_storage = SQLiteReportStorage(database_url)
    first_storage.save(report.report_id, report)
    second_storage = SQLiteReportStorage(database_url)

    assert second_storage.exists(report.report_id)
    assert second_storage.get(report.report_id) == report


def test_sqlite_storage_preserves_citation_decimal_types(tmp_path) -> None:
    company = CompanyDataFactory.create()
    report = DecisionEngine(RuleRegistry()).evaluate(company)
    annotated_mandatory: list[RuleResult] = EvidenceMapper().annotate(
        report.mandatory_results,
        company,
    )
    report = report.model_copy(update={"mandatory_results": annotated_mandatory})
    database_url = f"sqlite:///{tmp_path / 'reports.db'}"

    storage = SQLiteReportStorage(database_url)
    storage.save(report.report_id, report)
    reloaded = storage.get(report.report_id)

    assert reloaded is not None
    citation = reloaded.mandatory_results[0].source_citation
    assert citation is not None
    expected_value = company.financials.fiscal_years[-3].net_tangible_assets.value
    assert citation.extracted_values[0].value == expected_value
    assert type(citation.extracted_values[0].value) is type(
        expected_value
    )
