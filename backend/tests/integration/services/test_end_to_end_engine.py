"""
backend/tests/integration/services/test_end_to_end_engine.py

Integration tests for the deterministic CompanyData to IPOReport pipeline.
"""

from __future__ import annotations

from app.engine.decision_engine import DecisionEngine
from app.models.enums import IPOStatus, Verdict
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


class TestDeterministicPipeline:
    """DecisionEngine integrates rules, evidence, progress, and gaps."""

    def test_eligible_company_produces_eligible_report(self) -> None:
        report = DecisionEngine(RuleRegistry()).evaluate(CompanyDataFactory.create())

        assert report.status == IPOStatus.ELIGIBLE
        assert report.mandatory_progress.passed == 11
        assert report.mandatory_progress.failed == 0
        assert report.gap_analysis == []
        assert all(result.verdict == Verdict.PASS for result in report.mandatory_results)

    def test_not_eligible_company_produces_failed_mandatory_gaps(self) -> None:
        report = DecisionEngine(RuleRegistry()).evaluate(
            CompanyDataFactory.create_not_eligible()
        )

        assert report.status == IPOStatus.NOT_ELIGIBLE
        assert report.mandatory_progress.failed > 0
        assert report.gap_analysis
        assert {gap.rule_id for gap in report.gap_analysis}.issubset(
            set(report.mandatory_progress.failed_rule_ids)
        )

    def test_low_confidence_company_produces_needs_review_report(self) -> None:
        report = DecisionEngine(RuleRegistry()).evaluate(
            CompanyDataFactory.create_needs_review()
        )

        assert report.status == IPOStatus.NEEDS_REVIEW
        assert report.mandatory_progress.inconclusive > 0
        assert any(
            result.verdict == Verdict.INCONCLUSIVE for result in report.mandatory_results
        )
        assert all(result.verdict != Verdict.FAIL for result in report.mandatory_results)
