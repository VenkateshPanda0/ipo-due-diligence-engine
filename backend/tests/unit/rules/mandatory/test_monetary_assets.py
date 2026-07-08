"""
backend/tests/unit/rules/mandatory/test_monetary_assets.py

Unit tests for MONETARY_ASSETS_50PCT mandatory rule (M3-021).

100% branch coverage for MonetaryAssetsRule.evaluate():
  - PASS: all 3 years under 50%
  - PASS: exactly 50% boundary
  - FAIL: one year over 50%
  - FAIL: zero NTA with positive monetary assets (automatic fail)
  - PASS: zero NTA and zero monetary assets (0% ratio)
  - INCONCLUSIVE: fewer than 3 years
  - INCONCLUSIVE: LOW confidence NTA
  - INCONCLUSIVE: LOW confidence monetary assets
"""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import ConfidenceLevel, Verdict
from app.rules.mandatory.net_tangible_assets import MonetaryAssetsRule
from tests.fixtures.company_data_factory import CompanyDataFactory


def _fy_with_ratio(
    label: str,
    nta: Decimal,
    monetary: Decimal,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> object:
    """Create a FiscalYear with explicit NTA and monetary assets."""
    from app.models.company_data import FiscalYear
    from app.models.enums import ExtractionMethod
    from app.models.extracted_value import ExtractedValue

    def ev(v: Decimal) -> ExtractedValue[Decimal]:
        extraction_method = (
            ExtractionMethod.OCR
            if confidence == ConfidenceLevel.LOW
            else ExtractionMethod.MANUAL
        )
        return ExtractedValue(
            value=v,
            source_document="test.pdf",
            extraction_method=extraction_method,
            confidence=confidence,
        )

    return FiscalYear(
        year_label=label,
        revenue=ev(Decimal("100")),
        operating_profit=ev(Decimal("20")),
        pat=ev(Decimal("14")),
        net_worth=ev(Decimal("50")),
        net_tangible_assets=ev(nta),
        monetary_assets=ev(monetary),
        total_assets=ev(Decimal("120")),
        total_liabilities=ev(Decimal("70")),
        paid_up_capital=ev(Decimal("10")),
        reserves_and_surplus=ev(Decimal("40")),
        ebitda=ev(Decimal("22")),
    )


class TestMonetaryAssetsPass:
    """MonetaryAssetsRule PASS scenarios."""

    def test_all_years_below_50_pct(self) -> None:
        # 10/45 = 22.2%
        company = CompanyDataFactory.create(
            net_tangible_assets=Decimal("45"),
            monetary_assets=Decimal("10"),
        )
        result = MonetaryAssetsRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_exactly_50_pct_passes(self) -> None:
        years = [_fy_with_ratio(f"FY{2022 + i}", Decimal("10"), Decimal("5")) for i in range(3)]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = MonetaryAssetsRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_zero_nta_zero_monetary_passes(self) -> None:
        years = [
            _fy_with_ratio("FY2022", Decimal("10"), Decimal("5")),
            _fy_with_ratio("FY2023", Decimal("0"), Decimal("0")),  # both zero → 0%
            _fy_with_ratio("FY2024", Decimal("10"), Decimal("5")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = MonetaryAssetsRule().evaluate(company)
        assert result.verdict == Verdict.PASS


class TestMonetaryAssetsFail:
    """MonetaryAssetsRule FAIL scenarios."""

    def test_one_year_over_50_pct(self) -> None:
        years = [
            _fy_with_ratio("FY2022", Decimal("10"), Decimal("4")),
            _fy_with_ratio("FY2023", Decimal("10"), Decimal("6")),  # 60% - FAIL
            _fy_with_ratio("FY2024", Decimal("10"), Decimal("4")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = MonetaryAssetsRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert "FY2023" in (result.gap or "")

    def test_all_years_over_50_pct(self) -> None:
        years = [_fy_with_ratio(f"FY{2022 + i}", Decimal("10"), Decimal("8")) for i in range(3)]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = MonetaryAssetsRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_zero_nta_positive_monetary_fails(self) -> None:
        years = [
            _fy_with_ratio("FY2022", Decimal("10"), Decimal("4")),
            _fy_with_ratio("FY2023", Decimal("0"), Decimal("5")),  # zero NTA + cash = FAIL
            _fy_with_ratio("FY2024", Decimal("10"), Decimal("4")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = MonetaryAssetsRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_just_over_50_pct_fails(self) -> None:
        years = [
            _fy_with_ratio(f"FY{2022 + i}", Decimal("10"), Decimal("5.01"))
            for i in range(3)
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = MonetaryAssetsRule().evaluate(company)
        assert result.verdict == Verdict.FAIL


class TestMonetaryAssetsInconclusive:
    """MonetaryAssetsRule INCONCLUSIVE scenarios."""

    def test_fewer_than_3_years_inconclusive(self) -> None:
        years = [_fy_with_ratio("FY2023", Decimal("10"), Decimal("4"))]
        company = CompanyDataFactory.create(fiscal_years=years, years_of_operation=1)
        result = MonetaryAssetsRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_nta_inconclusive(self) -> None:
        years = [
            _fy_with_ratio("FY2022", Decimal("10"), Decimal("4"), ConfidenceLevel.LOW),
            _fy_with_ratio("FY2023", Decimal("10"), Decimal("4")),
            _fy_with_ratio("FY2024", Decimal("10"), Decimal("4")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = MonetaryAssetsRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_monetary_assets_inconclusive(self) -> None:
        from app.models.company_data import FiscalYear
        from app.models.enums import ExtractionMethod
        from app.models.extracted_value import ExtractedValue

        def ev_high(v: Decimal) -> ExtractedValue[Decimal]:
            return ExtractedValue(
                value=v,
                source_document="test.pdf",
                extraction_method=ExtractionMethod.MANUAL,
                confidence=ConfidenceLevel.HIGH,
            )

        def ev_low(v: Decimal) -> ExtractedValue[Decimal]:
            return ExtractedValue(
                value=v,
                source_document="test.pdf",
                extraction_method=ExtractionMethod.OCR,
                confidence=ConfidenceLevel.LOW,
            )

        years = [
            FiscalYear(
                year_label="FY2022",
                revenue=ev_high(Decimal("100")),
                operating_profit=ev_high(Decimal("20")),
                pat=ev_high(Decimal("14")),
                net_worth=ev_high(Decimal("50")),
                net_tangible_assets=ev_high(Decimal("10")),
                monetary_assets=ev_low(Decimal("4")),  # LOW confidence
                total_assets=ev_high(Decimal("120")),
                total_liabilities=ev_high(Decimal("70")),
                paid_up_capital=ev_high(Decimal("10")),
                reserves_and_surplus=ev_high(Decimal("40")),
                ebitda=ev_high(Decimal("22")),
            ),
            _fy_with_ratio("FY2023", Decimal("10"), Decimal("4")),
            _fy_with_ratio("FY2024", Decimal("10"), Decimal("4")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = MonetaryAssetsRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE
