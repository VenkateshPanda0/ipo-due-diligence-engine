"""
backend/tests/unit/engine/test_rules_engine.py

Unit tests for RulesEngine (M3-032).

Tests: evaluate_all returns 16 results, evaluate_mandatory/advisory filters,
exception isolation (one broken rule doesn't abort others), result ordering,
INCONCLUSIVE fallback on rule exception.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.engine.rules_engine import RulesEngine
from app.models.company_data import CompanyData
from app.models.enums import RuleCategory, Verdict
from app.rules.base_rule import BaseRule
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


class TestRulesEngineEvaluateAll:
    """Tests for evaluate_all()."""

    def test_returns_16_results(self, registry: RuleRegistry, company: CompanyData) -> None:
        engine = RulesEngine(registry)
        results = engine.evaluate_all(company)
        assert len(results) == 16

    def test_all_rule_ids_present(self, registry: RuleRegistry, company: CompanyData) -> None:
        engine = RulesEngine(registry)
        results = engine.evaluate_all(company)
        result_ids = {r.rule_id for r in results}
        registry_ids = set(registry.get_rule_ids())
        assert result_ids == registry_ids

    def test_result_order_matches_registry(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        engine = RulesEngine(registry)
        results = engine.evaluate_all(company)
        result_ids = [r.rule_id for r in results]
        registry_ids = registry.get_rule_ids()
        assert result_ids == registry_ids

    def test_all_verdicts_defined(self, registry: RuleRegistry, company: CompanyData) -> None:
        engine = RulesEngine(registry)
        results = engine.evaluate_all(company)
        for result in results:
            assert result.verdict in (Verdict.PASS, Verdict.FAIL, Verdict.INCONCLUSIVE)

    def test_eligible_company_all_mandatory_pass(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        engine = RulesEngine(registry)
        results = engine.evaluate_all(company)
        mandatory = [r for r in results if r.category == RuleCategory.MANDATORY]
        assert all(r.verdict == Verdict.PASS for r in mandatory)

    def test_ineligible_company_has_mandatory_fails(self, registry: RuleRegistry) -> None:
        company = CompanyDataFactory.create_not_eligible()
        engine = RulesEngine(registry)
        results = engine.evaluate_all(company)
        mandatory = [r for r in results if r.category == RuleCategory.MANDATORY]
        assert any(r.verdict == Verdict.FAIL for r in mandatory)


class TestRulesEngineEvaluateMandatory:
    """Tests for evaluate_mandatory()."""

    def test_returns_11_results(self, registry: RuleRegistry, company: CompanyData) -> None:
        engine = RulesEngine(registry)
        results = engine.evaluate_mandatory(company)
        assert len(results) == 11

    def test_all_results_mandatory_category(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        engine = RulesEngine(registry)
        results = engine.evaluate_mandatory(company)
        assert all(r.category == RuleCategory.MANDATORY for r in results)


class TestRulesEngineEvaluateAdvisory:
    """Tests for evaluate_advisory()."""

    def test_returns_5_results(self, registry: RuleRegistry, company: CompanyData) -> None:
        engine = RulesEngine(registry)
        results = engine.evaluate_advisory(company)
        assert len(results) == 5

    def test_all_results_advisory_category(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        engine = RulesEngine(registry)
        results = engine.evaluate_advisory(company)
        assert all(r.category == RuleCategory.ADVISORY for r in results)


class TestRulesEngineExceptionIsolation:
    """Exception in one rule must not abort evaluation of others."""

    def test_exception_in_one_rule_produces_inconclusive(
        self, company: CompanyData
    ) -> None:
        """A rule that raises an exception produces an INCONCLUSIVE result."""
        failing_rule = MagicMock(spec=BaseRule)
        failing_rule.rule_id = "FAILING_RULE"
        failing_rule.category = RuleCategory.MANDATORY
        failing_rule.evaluate.side_effect = RuntimeError("Simulated programming error")
        failing_rule.metadata.section = "Regulation 99"
        failing_rule.metadata.description = "Test rule"
        failing_rule._required_value = "test"

        # Patch the registry to inject the failing rule at the start
        normal_registry = RuleRegistry()
        mock_registry = MagicMock()
        mock_registry.get_all_rules.return_value = (
            [failing_rule] + normal_registry.get_all_rules()
        )

        engine_with_broken = RulesEngine(mock_registry)
        results = engine_with_broken.evaluate_all(company)

        # The failing rule should have an INCONCLUSIVE result
        failing_result = next(r for r in results if r.rule_id == "FAILING_RULE")
        assert failing_result.verdict == Verdict.INCONCLUSIVE
        assert "internal error" in failing_result.explanation.lower()

        # All other rules should still have valid verdicts
        other_results = [r for r in results if r.rule_id != "FAILING_RULE"]
        assert len(other_results) == 16

    def test_other_rules_still_execute_after_exception(
        self, company: CompanyData
    ) -> None:
        """After one rule fails, subsequent rules still run and produce results."""
        failing_rule = MagicMock(spec=BaseRule)
        failing_rule.rule_id = "FIRST_RULE"
        failing_rule.category = RuleCategory.MANDATORY
        failing_rule.evaluate.side_effect = ValueError("Broken")
        failing_rule.metadata.section = "Section 1"
        failing_rule.metadata.description = "First rule"
        failing_rule._required_value = "test"

        normal_registry = RuleRegistry()
        mock_registry = MagicMock()
        mock_registry.get_all_rules.return_value = (
            [failing_rule] + normal_registry.get_all_rules()
        )

        engine = RulesEngine(mock_registry)
        results = engine.evaluate_all(company)

        # Should have 17 results total (1 failing + 16 normal)
        assert len(results) == 17
        non_failing = [r for r in results if r.rule_id != "FIRST_RULE"]
        assert all(r.verdict in (Verdict.PASS, Verdict.FAIL, Verdict.INCONCLUSIVE)
                   for r in non_failing)


class TestRulesEngineReusability:
    """Engine instances must be reusable across multiple evaluations."""

    def test_same_engine_evaluates_multiple_companies(
        self, registry: RuleRegistry
    ) -> None:
        engine = RulesEngine(registry)
        company1 = CompanyDataFactory.create()
        company2 = CompanyDataFactory.create_not_eligible()

        results1 = engine.evaluate_all(company1)
        results2 = engine.evaluate_all(company2)

        # Same engine, different results based on input
        assert len(results1) == 16
        assert len(results2) == 16

        mandatory1 = [r for r in results1 if r.category == RuleCategory.MANDATORY]
        mandatory2 = [r for r in results2 if r.category == RuleCategory.MANDATORY]

        assert all(r.verdict == Verdict.PASS for r in mandatory1)
        assert any(r.verdict == Verdict.FAIL for r in mandatory2)

    def test_deterministic_output_for_same_input(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        engine = RulesEngine(registry)
        results_a = engine.evaluate_all(company)
        results_b = engine.evaluate_all(company)

        # Verdicts must be identical
        verdicts_a = [r.verdict for r in results_a]
        verdicts_b = [r.verdict for r in results_b]
        assert verdicts_a == verdicts_b
