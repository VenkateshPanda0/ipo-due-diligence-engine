"""
backend/tests/unit/rules/mandatory/test_profitability.py

Unit tests for AVG_OPERATING_PROFIT_15CR mandatory rule (M3-022).

100% branch coverage for ProfitabilityRule.evaluate():
  - PASS: high profit across all years
  - PASS: exactly ₹15 Cr boundary
  - FAIL: low average
  - FAIL: just below ₹15 Cr
  - 3-year company (best 3 of 3)
  - 5-year company with 2 bad years (best 3 of 5 selection verified)
  - INCONCLUSIVE: fewer than 3 years
  - INCONCLUSIVE: LOW confidence in a selected year
  - Negative profits handled
  - Gap calculation verified
"""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import ConfidenceLevel, Verdict
from app.rules.mandatory.profitability import ProfitabilityRule
from tests.fixtures.company_data_factory import CompanyDataFactory, _make_fiscal_year


class TestProfitabilityRuleMetadata:
    def test_rule_id(self) -> None:
        assert ProfitabilityRule().rule_id == "AVG_OPERATING_PROFIT_15CR"

    def test_regulation_reference(self) -> None:
        meta = ProfitabilityRule().metadata
        assert "26(1)" in meta.section
        assert "(b)" in (meta.clause or "")


class TestProfitabilityRulePass:
    def test_all_years_above_15cr(self) -> None:
        company = CompanyDataFactory.create(operating_profit=Decimal("20"))
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_exactly_15cr_average_passes(self) -> None:
        company = CompanyDataFactory.create(operating_profit=Decimal("15"))
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_best_3_of_5_selection_passes(self) -> None:
        """Best 3 of 5: select 3 years at 20, ignore 2 at 5. Avg = 20 ≥ 15."""
        years = [
            _make_fiscal_year("FY2020", operating_profit=Decimal("20")),
            _make_fiscal_year("FY2021", operating_profit=Decimal("20")),
            _make_fiscal_year("FY2022", operating_profit=Decimal("5")),  # not selected
            _make_fiscal_year("FY2023", operating_profit=Decimal("5")),  # not selected
            _make_fiscal_year("FY2024", operating_profit=Decimal("20")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_3_year_company_best_3_of_3(self) -> None:
        """Company with exactly 3 years uses best 3 of 3."""
        years = [
            _make_fiscal_year("FY2022", operating_profit=Decimal("18")),
            _make_fiscal_year("FY2023", operating_profit=Decimal("16")),
            _make_fiscal_year("FY2024", operating_profit=Decimal("20")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years, years_of_operation=3)
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_large_profit_clearly_passes(self) -> None:
        company = CompanyDataFactory.create(operating_profit=Decimal("100"))
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None


class TestProfitabilityRuleFail:
    def test_average_below_15cr_fails(self) -> None:
        company = CompanyDataFactory.create(operating_profit=Decimal("10"))
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_just_below_15cr_fails(self) -> None:
        company = CompanyDataFactory.create(operating_profit=Decimal("14.99"))
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_gap_computed_correctly(self) -> None:
        """Average = 10, threshold = 15, gap = 5."""
        company = CompanyDataFactory.create(operating_profit=Decimal("10"))
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        assert "5.00" in result.gap

    def test_negative_profits_fail(self) -> None:
        company = CompanyDataFactory.create(operating_profit=Decimal("-5"))
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_best_3_of_5_still_fails(self) -> None:
        """Even best 3 of 5 average is below threshold."""
        years = [
            _make_fiscal_year("FY2020", operating_profit=Decimal("12")),
            _make_fiscal_year("FY2021", operating_profit=Decimal("11")),
            _make_fiscal_year("FY2022", operating_profit=Decimal("10")),
            _make_fiscal_year("FY2023", operating_profit=Decimal("9")),
            _make_fiscal_year("FY2024", operating_profit=Decimal("8")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.FAIL


class TestProfitabilityRuleInconclusive:
    def test_only_2_years_inconclusive(self) -> None:
        years = [
            _make_fiscal_year("FY2023", operating_profit=Decimal("20")),
            _make_fiscal_year("FY2024", operating_profit=Decimal("20")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years, years_of_operation=2)
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_only_1_year_inconclusive(self) -> None:
        years = [_make_fiscal_year("FY2024", operating_profit=Decimal("20"))]
        company = CompanyDataFactory.create(fiscal_years=years, years_of_operation=1)
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_in_selected_year_inconclusive(self) -> None:
        """If a best-3 year has LOW confidence, result is INCONCLUSIVE."""
        years = [
            _make_fiscal_year("FY2022", operating_profit=Decimal("20"),
                              confidence=ConfidenceLevel.LOW),
            _make_fiscal_year("FY2023", operating_profit=Decimal("20")),
            _make_fiscal_year("FY2024", operating_profit=Decimal("20")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_not_in_best_3_does_not_affect(self) -> None:
        """LOW confidence in a year outside the best-3 does not cause INCONCLUSIVE."""
        years = [
            _make_fiscal_year("FY2020", operating_profit=Decimal("5"),
                              confidence=ConfidenceLevel.LOW),  # not in best 3
            _make_fiscal_year("FY2021", operating_profit=Decimal("5"),
                              confidence=ConfidenceLevel.LOW),  # not in best 3
            _make_fiscal_year("FY2022", operating_profit=Decimal("20")),
            _make_fiscal_year("FY2023", operating_profit=Decimal("20")),
            _make_fiscal_year("FY2024", operating_profit=Decimal("20")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = ProfitabilityRule().evaluate(company)
        assert result.verdict == Verdict.PASS
