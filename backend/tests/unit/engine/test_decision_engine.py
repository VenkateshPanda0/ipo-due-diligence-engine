"""
backend/tests/unit/engine/test_decision_engine.py

Unit tests for DecisionEngine milestone 4 behavior.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.engine.decision_engine import DecisionEngine
from app.engine.rules_engine import RulesEngine
from app.models.company_data import CompanyData
from app.models.enums import IPOStatus, RuleCategory, Verdict
from app.models.ipo_report import EligibilityProgress, IPOReport
from app.models.rule_result import RuleResult
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


def _result(
    rule_id: str,
    verdict: Verdict,
    category: RuleCategory = RuleCategory.MANDATORY,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        verdict=verdict,
        category=category,
        regulation_reference="Test Regulation 1",
        description=f"{rule_id} description",
        required_value="Test requirement",
        actual_value="Test actual",
        explanation=f"{rule_id} explanation",
    )


class TestDecisionEngineStatus:
    """Status determination is a deterministic mandatory-rule rollup."""

    def test_all_pass_returns_eligible(self) -> None:
        results = [_result("A", Verdict.PASS), _result("B", Verdict.PASS)]
        assert DecisionEngine.determine_status(results) == IPOStatus.ELIGIBLE

    def test_single_fail_returns_not_eligible(self) -> None:
        results = [_result("A", Verdict.PASS), _result("B", Verdict.FAIL)]
        assert DecisionEngine.determine_status(results) == IPOStatus.NOT_ELIGIBLE

    def test_single_inconclusive_returns_needs_review(self) -> None:
        results = [_result("A", Verdict.PASS), _result("B", Verdict.INCONCLUSIVE)]
        assert DecisionEngine.determine_status(results) == IPOStatus.NEEDS_REVIEW

    def test_fail_takes_precedence_over_inconclusive(self) -> None:
        results = [_result("A", Verdict.FAIL), _result("B", Verdict.INCONCLUSIVE)]
        assert DecisionEngine.determine_status(results) == IPOStatus.NOT_ELIGIBLE

    def test_empty_results_are_eligible_by_vacuous_rollup(self) -> None:
        assert DecisionEngine.determine_status([]) == IPOStatus.ELIGIBLE


class TestDecisionEngineClassification:
    """RuleResult category splitting preserves input order."""

    def test_classifies_mandatory_and_advisory_results(self) -> None:
        mandatory_a = _result("MANDATORY_A", Verdict.PASS)
        advisory = _result("ADVISORY", Verdict.FAIL, RuleCategory.ADVISORY)
        mandatory_b = _result("MANDATORY_B", Verdict.INCONCLUSIVE)

        mandatory, advisory_results = DecisionEngine.classify_results(
            [mandatory_a, advisory, mandatory_b]
        )

        assert mandatory == [mandatory_a, mandatory_b]
        assert advisory_results == [advisory]

    def test_empty_input_returns_empty_groups(self) -> None:
        assert DecisionEngine.classify_results([]) == ([], [])


class TestDecisionEngineProgress:
    """Progress counts are objective counts, not weighted scores."""

    def test_progress_counts_and_failed_ids_are_correct(self) -> None:
        results = [
            _result("PASS_A", Verdict.PASS),
            _result("FAIL_A", Verdict.FAIL),
            _result("INCONCLUSIVE_A", Verdict.INCONCLUSIVE),
            _result("FAIL_B", Verdict.FAIL),
        ]

        progress = DecisionEngine.compute_progress(results)

        assert progress.total_rules == 4
        assert progress.passed == 1
        assert progress.failed == 2
        assert progress.inconclusive == 1
        assert progress.pass_percentage == Decimal("25.00")
        assert progress.failed_rule_ids == ["FAIL_A", "FAIL_B"]

    def test_empty_progress_uses_zero_percentage(self) -> None:
        progress = DecisionEngine.compute_progress([])

        assert progress.total_rules == 0
        assert progress.passed == 0
        assert progress.failed == 0
        assert progress.inconclusive == 0
        assert progress.pass_percentage == Decimal("0")
        assert progress.failed_rule_ids == []

    def test_progress_model_rejects_inconsistent_counts(self) -> None:
        with pytest.raises(ValidationError):
            EligibilityProgress(
                total_rules=2,
                passed=1,
                failed=0,
                inconclusive=0,
                pass_percentage=Decimal("50"),
                failed_rule_ids=[],
            )


class TestDecisionEngineObservations:
    """Observation generation surfaces deterministic non-blocking patterns."""

    def test_observations_for_eligible_company_include_positive_signal(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        results = RulesEngine(registry).evaluate_all(company)
        mandatory, advisory = DecisionEngine.classify_results(results)

        observations = DecisionEngine.generate_observations(company, mandatory, advisory)

        assert any("All 11 mandatory" in observation for observation in observations)

    def test_observations_include_young_company_and_criminal_litigation(self) -> None:
        company = CompanyDataFactory.create(
            years_of_operation=2,
            has_criminal_cases=True,
        )
        observations = DecisionEngine.generate_observations(company, [], [])

        assert any("2 year(s)" in observation for observation in observations)
        assert any("Criminal litigation" in observation for observation in observations)


class TestDecisionEngineReportAssembly:
    """Full report assembly populates the IPOReport aggregate."""

    def test_evaluate_returns_complete_report(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        report = DecisionEngine(registry).evaluate(company)

        assert isinstance(report, IPOReport)
        assert report.company_name == company.identification.company_name
        assert report.status == IPOStatus.ELIGIBLE
        assert report.mandatory_progress.total_rules == 11
        assert report.advisory_progress.total_rules == 5
        assert len(report.mandatory_results) == 11
        assert len(report.advisory_results) == 5
        assert report.ruleset_version == company.ruleset_version

    def test_report_ids_are_unique(self, registry: RuleRegistry, company: CompanyData) -> None:
        engine = DecisionEngine(registry)

        first = engine.evaluate(company)
        second = engine.evaluate(company)

        assert first.report_id != second.report_id

    def test_report_is_immutable(self, registry: RuleRegistry, company: CompanyData) -> None:
        report = DecisionEngine(registry).evaluate(company)

        with pytest.raises(ValidationError):
            report.status = IPOStatus.NOT_ELIGIBLE
