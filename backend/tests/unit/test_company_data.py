"""
backend/tests/unit/test_company_data.py

Unit tests for CompanyData canonical schema (M2-025).

Tests: construction, immutability, chronological FY ordering validation,
JSON round-trip, factory integration.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.company_data import (
    CompanyIdentification,
    FinancialHistory,
)
from tests.fixtures.company_data_factory import CompanyDataFactory, _make_fiscal_year


class TestCompanyIdentification:
    """Tests for CompanyIdentification sub-model."""

    def test_valid_construction(self) -> None:
        ident = CompanyIdentification(
            company_name="Test Corp",
            cin="L17110MH2000PLC019786",
            industry="Manufacturing",
            incorporation_date=date(2000, 4, 1),
            registered_office="Mumbai",
        )
        assert ident.company_name == "Test Corp"

    def test_invalid_cin_raises(self) -> None:
        with pytest.raises(ValidationError, match="Invalid CIN"):
            CompanyIdentification(
                company_name="Test Corp",
                cin="INVALID",
                industry="Manufacturing",
                incorporation_date=date(2000, 4, 1),
                registered_office="Mumbai",
            )

    def test_valid_cin_variants(self) -> None:
        # Both L and U prefixes are valid
        for prefix in ("L", "U"):
            ident = CompanyIdentification(
                company_name="Test Corp",
                cin=f"{prefix}17110MH2000PLC019786",
                industry="Manufacturing",
                incorporation_date=date(2000, 4, 1),
                registered_office="Mumbai",
            )
            assert ident.cin.startswith(prefix)

    def test_immutability(self) -> None:
        ident = CompanyIdentification(
            company_name="Test Corp",
            cin="L17110MH2000PLC019786",
            industry="Manufacturing",
            incorporation_date=date(2000, 4, 1),
            registered_office="Mumbai",
        )
        with pytest.raises(ValidationError):
            ident.company_name = "Changed"  # type: ignore[misc]


class TestFinancialHistory:
    """Tests for FinancialHistory chronological ordering."""

    def test_valid_chronological_order(self) -> None:
        years = [_make_fiscal_year(f"FY{2020 + i}") for i in range(3)]
        history = FinancialHistory(fiscal_years=years, years_of_operation=3)
        assert len(history.fiscal_years) == 3

    def test_out_of_order_raises(self) -> None:
        years = [
            _make_fiscal_year("FY2022"),
            _make_fiscal_year("FY2021"),  # out of order
            _make_fiscal_year("FY2023"),
        ]
        with pytest.raises(ValidationError, match="chronological"):
            FinancialHistory(fiscal_years=years, years_of_operation=3)

    def test_duplicate_labels_raise(self) -> None:
        years = [
            _make_fiscal_year("FY2022"),
            _make_fiscal_year("FY2022"),  # duplicate
        ]
        with pytest.raises(ValidationError, match="unique"):
            FinancialHistory(fiscal_years=years, years_of_operation=2)

    def test_single_year_allowed(self) -> None:
        history = FinancialHistory(
            fiscal_years=[_make_fiscal_year("FY2024")],
            years_of_operation=1,
        )
        assert len(history.fiscal_years) == 1


class TestCompanyData:
    """Tests for the root CompanyData model."""

    def test_factory_produces_valid_company(self) -> None:
        company = CompanyDataFactory.create()
        assert company.identification.company_name == "Acme Industries Pvt Ltd"
        assert company.financials.years_of_operation == 5
        assert len(company.financials.fiscal_years) == 5

    def test_immutability_top_level(self) -> None:
        company = CompanyDataFactory.create()
        with pytest.raises(ValidationError):
            company.identification = company.identification  # type: ignore[misc]

    def test_ruleset_version_default(self) -> None:
        company = CompanyDataFactory.create()
        assert company.ruleset_version.version == "1.0.0"

    def test_json_round_trip(self) -> None:
        company = CompanyDataFactory.create()
        data = company.model_dump()
        # Verify nested ExtractedValue fields are present
        assert "value" in data["financials"]["fiscal_years"][0]["operating_profit"]
        assert data["financials"]["fiscal_years"][0]["operating_profit"]["confidence"] == "high"

    def test_override_years_of_operation(self) -> None:
        company = CompanyDataFactory.create(years_of_operation=2)
        assert company.financials.years_of_operation == 2

    def test_override_operating_profit(self) -> None:
        company = CompanyDataFactory.create(operating_profit=Decimal("5"))
        for fy in company.financials.fiscal_years:
            assert fy.operating_profit.value == Decimal("5")

    def test_custom_fiscal_years(self) -> None:
        custom_years = [_make_fiscal_year(f"FY{2021 + i}") for i in range(3)]
        company = CompanyDataFactory.create(fiscal_years=custom_years)
        assert len(company.financials.fiscal_years) == 3
        assert company.financials.fiscal_years[0].year_label == "FY2021"

    def test_promoter_holding_range(self) -> None:
        company = CompanyDataFactory.create(holding_percentage=Decimal("60"))
        assert company.promoter.holding_percentage.value == Decimal("60")

    def test_governance_data_present(self) -> None:
        company = CompanyDataFactory.create()
        assert company.governance.total_directors.value == 6
        assert company.governance.independent_directors.value == 3
        assert company.governance.audit_committee.total_members.value == 4

    def test_litigation_data_present(self) -> None:
        company = CompanyDataFactory.create()
        assert company.litigation.has_criminal_cases.value is False
        assert company.litigation.total_exposure.value == Decimal("0")

    def test_auditor_data_present(self) -> None:
        company = CompanyDataFactory.create()
        assert company.auditor.has_qualifications.value is False
        assert company.auditor.has_modified_opinion.value is False
