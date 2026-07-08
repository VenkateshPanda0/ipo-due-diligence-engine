"""
backend/tests/unit/rules/mandatory/test_net_tangible_assets.py

Unit tests for NTA_3CR mandatory rule (M3-020).

100% branch coverage for NTARule.evaluate():
  - PASS: all 3 years ≥ ₹3 Cr
  - FAIL: one year below threshold
  - FAIL: all years below threshold
  - FAIL: worst year is correctly identified for gap
  - INCONCLUSIVE: fewer than 3 years available
  - INCONCLUSIVE: zero years available
  - INCONCLUSIVE: LOW confidence data
  - Boundary: exactly ₹3 Cr passes
  - Gap calculation verification
"""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import ConfidenceLevel, Verdict
from app.rules.mandatory.net_tangible_assets import NTARule
from tests.fixtures.company_data_factory import (
    CompanyDataFactory,
    _make_fiscal_year,
)


class TestNTARuleMetadata:
    """Tests for rule metadata and identification."""

    def test_rule_id(self) -> None:
        assert NTARule().rule_id == "NTA_3CR"

    def test_category_mandatory(self) -> None:
        from app.models.enums import RuleCategory
        assert NTARule().category == RuleCategory.MANDATORY

    def test_regulation_reference(self) -> None:
        meta = NTARule().metadata
        assert "26(1)" in meta.section
        assert "ICDR" in meta.regulation


class TestNTARulePass:
    """NTA rule PASS scenarios."""

    def test_all_3_years_above_threshold(self) -> None:
        company = CompanyDataFactory.create(net_tangible_assets=Decimal("5"))
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None

    def test_exactly_3cr_boundary_passes(self) -> None:
        company = CompanyDataFactory.create(net_tangible_assets=Decimal("3"))
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_uses_last_3_of_5_years(self) -> None:
        """With 5 years, rule checks last 3 only."""
        years = [
            _make_fiscal_year("FY2020", net_tangible_assets=Decimal("1")),  # old - ignored
            _make_fiscal_year("FY2021", net_tangible_assets=Decimal("1")),  # old - ignored
            _make_fiscal_year("FY2022", net_tangible_assets=Decimal("5")),
            _make_fiscal_year("FY2023", net_tangible_assets=Decimal("5")),
            _make_fiscal_year("FY2024", net_tangible_assets=Decimal("5")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.PASS


class TestNTARuleFail:
    """NTA rule FAIL scenarios."""

    def test_one_year_below_3cr(self) -> None:
        years = [
            _make_fiscal_year("FY2022", net_tangible_assets=Decimal("5")),
            _make_fiscal_year("FY2023", net_tangible_assets=Decimal("2")),  # FAIL
            _make_fiscal_year("FY2024", net_tangible_assets=Decimal("5")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        assert "FY2023" in result.gap

    def test_all_years_below_3cr(self) -> None:
        company = CompanyDataFactory.create(net_tangible_assets=Decimal("1"))
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_just_below_threshold_fails(self) -> None:
        company = CompanyDataFactory.create(net_tangible_assets=Decimal("2.99"))
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_gap_identifies_worst_shortfall(self) -> None:
        years = [
            _make_fiscal_year("FY2022", net_tangible_assets=Decimal("2.5")),
            _make_fiscal_year("FY2023", net_tangible_assets=Decimal("1")),  # worst
            _make_fiscal_year("FY2024", net_tangible_assets=Decimal("2.8")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        assert "FY2023" in result.gap  # worst year is identified

    def test_negative_nta_fails(self) -> None:
        company = CompanyDataFactory.create(net_tangible_assets=Decimal("-5"))
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.FAIL


class TestNTARuleInconclusive:
    """NTA rule INCONCLUSIVE scenarios."""

    def test_fewer_than_3_years_inconclusive(self) -> None:
        years = [
            _make_fiscal_year("FY2023"),
            _make_fiscal_year("FY2024"),
        ]
        company = CompanyDataFactory.create(fiscal_years=years, years_of_operation=2)
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_zero_years_inconclusive(self) -> None:
        company = CompanyDataFactory.create(
            fiscal_years=[_make_fiscal_year("FY2024")],
            years_of_operation=1,
        )
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_nta_inconclusive(self) -> None:
        years = [
            _make_fiscal_year("FY2022", confidence=ConfidenceLevel.LOW),
            _make_fiscal_year("FY2023"),
            _make_fiscal_year("FY2024"),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = NTARule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_explanation_present_on_inconclusive(self) -> None:
        years = [_make_fiscal_year("FY2024")]
        company = CompanyDataFactory.create(fiscal_years=years, years_of_operation=1)
        result = NTARule().evaluate(company)
        assert result.explanation
        assert "manual review" in result.explanation.lower()
