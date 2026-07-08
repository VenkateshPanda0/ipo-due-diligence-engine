"""
backend/tests/unit/engine/test_gap_planner.py

Unit tests for GapPlanner remediation and projection behavior.
"""

from __future__ import annotations

from decimal import Decimal

from app.engine.gap_planner import GapPlanner
from app.engine.rules_engine import RulesEngine
from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.ipo_report import GapAnalysisItem
from app.models.rule_result import RuleResult
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory, _make_fiscal_year


def _failed_result(
    rule_id: str,
    registry: RuleRegistry,
    company: CompanyData,
) -> RuleResult:
    results = RulesEngine(registry).evaluate_all(company)
    result = next(item for item in results if item.rule_id == rule_id)
    assert result.verdict == Verdict.FAIL
    return result


class TestGapPlanner:
    """GapPlanner creates actionable items for failed mandatory rules."""

    def test_creates_gap_item_for_failed_profitability(self, registry: RuleRegistry) -> None:
        company = CompanyDataFactory.create(operating_profit=Decimal("10"))
        result = _failed_result("AVG_OPERATING_PROFIT_15CR", registry, company)

        [gap] = GapPlanner().generate([result], company)

        assert isinstance(gap, GapAnalysisItem)
        assert gap.rule_id == "AVG_OPERATING_PROFIT_15CR"
        assert "below" in gap.gap_size
        assert gap.remediation_steps
        assert gap.current_value == result.actual_value
        assert gap.required_value == result.required_value

    def test_projects_earliest_fy_for_growing_profitability_gap(
        self, registry: RuleRegistry
    ) -> None:
        fiscal_years = [
            _make_fiscal_year("FY2022", operating_profit=Decimal("5")),
            _make_fiscal_year("FY2023", operating_profit=Decimal("9")),
            _make_fiscal_year("FY2024", operating_profit=Decimal("13")),
        ]
        company = CompanyDataFactory.create(fiscal_years=fiscal_years)
        result = _failed_result("AVG_OPERATING_PROFIT_15CR", registry, company)

        [gap] = GapPlanner().generate([result], company)

        assert gap.earliest_eligible_fy == "FY2025"

    def test_flat_profitability_trend_is_undetermined(self, registry: RuleRegistry) -> None:
        company = CompanyDataFactory.create(operating_profit=Decimal("10"))
        result = _failed_result("AVG_OPERATING_PROFIT_15CR", registry, company)

        [gap] = GapPlanner().generate([result], company)

        assert gap.earliest_eligible_fy == "Undetermined"

    def test_non_failed_results_do_not_create_gap_items(self, registry: RuleRegistry) -> None:
        company = CompanyDataFactory.create()
        results = RulesEngine(registry).evaluate_mandatory(company)

        gaps = GapPlanner().generate(results, company)

        assert gaps == []

    def test_generic_remediation_exists_for_unknown_failed_rule(
        self, registry: RuleRegistry
    ) -> None:
        company = CompanyDataFactory.create_not_eligible()
        result = _failed_result("NTA_3CR", registry, company).model_copy(
            update={"rule_id": "UNKNOWN_RULE"}
        )

        [gap] = GapPlanner().generate([result], company)

        assert gap.rule_id == "UNKNOWN_RULE"
        assert gap.remediation_steps
