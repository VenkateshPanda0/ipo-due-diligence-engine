"""
backend/tests/fixtures/company_data_factory.py

CompanyDataFactory — test data generation for CompanyData.

Provides a single factory function that creates fully valid CompanyData
instances with sensible defaults (profitable company, 5 years history,
good governance). Every financial field is wrapped in ExtractedValue with
HIGH confidence and MANUAL extraction method.

Supports keyword overrides for any top-level sub-model so that individual
tests can set up specific scenarios without constructing the entire object
from scratch.

Usage::

    from backend.tests.fixtures.company_data_factory import CompanyDataFactory

    # Eligible company (all defaults)
    company = CompanyDataFactory.create()

    # Override years_of_operation to test track record rule
    company = CompanyDataFactory.create(years_of_operation=2)

    # Override financial data to produce a FAIL on profitability
    company = CompanyDataFactory.create(avg_operating_profit=Decimal("10"))
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.models.company_data import (
    AuditCommittee,
    AuditorData,
    CompanyData,
    CompanyIdentification,
    FinancialHistory,
    FiscalYear,
    GovernanceData,
    IssueDetails,
    LitigationData,
    PromoterData,
    PromoterEntity,
    RelatedPartyData,
    RPTTransaction,
)
from app.models.enums import ConfidenceLevel, ExtractionMethod
from app.models.extracted_value import ExtractedValue
from app.models.ruleset_version import DEFAULT_RULESET_VERSION


def _ev(value: Any, confidence: ConfidenceLevel = ConfidenceLevel.HIGH) -> ExtractedValue[Any]:
    """Build an ExtractedValue wrapping the given value for test scenarios."""
    extraction_method = (
        ExtractionMethod.OCR
        if confidence == ConfidenceLevel.LOW
        else ExtractionMethod.MANUAL
    )
    return ExtractedValue(
        value=value,
        source_document="Annual_Report_Test.pdf",
        page_number=1,
        extraction_method=extraction_method,
        confidence=confidence,
    )


def _make_fiscal_year(
    label: str,
    revenue: Decimal = Decimal("100"),
    operating_profit: Decimal = Decimal("20"),
    pat: Decimal = Decimal("14"),
    net_worth: Decimal = Decimal("50"),
    net_tangible_assets: Decimal = Decimal("45"),
    monetary_assets: Decimal = Decimal("10"),
    total_assets: Decimal = Decimal("120"),
    total_liabilities: Decimal = Decimal("70"),
    paid_up_capital: Decimal = Decimal("10"),
    reserves_and_surplus: Decimal = Decimal("40"),
    ebitda: Decimal = Decimal("22"),
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> FiscalYear:
    """Build a FiscalYear with the given values, all wrapped in ExtractedValue."""
    return FiscalYear(
        year_label=label,
        revenue=_ev(revenue, confidence),
        operating_profit=_ev(operating_profit, confidence),
        pat=_ev(pat, confidence),
        net_worth=_ev(net_worth, confidence),
        net_tangible_assets=_ev(net_tangible_assets, confidence),
        monetary_assets=_ev(monetary_assets, confidence),
        total_assets=_ev(total_assets, confidence),
        total_liabilities=_ev(total_liabilities, confidence),
        paid_up_capital=_ev(paid_up_capital, confidence),
        reserves_and_surplus=_ev(reserves_and_surplus, confidence),
        ebitda=_ev(ebitda, confidence),
    )


class CompanyDataFactory:
    """Factory for creating test CompanyData instances.

    All defaults produce a company that passes every mandatory and advisory rule:
      - 5 fiscal years (FY2020–FY2024)
      - NTA ≥ ₹3 Cr each year
      - Monetary assets ≤ 50% of NTA each year
      - Average operating profit ≥ ₹15 Cr (best 3 of 5)
      - Net worth ≥ ₹1 Cr each year
      - Issue size ≤ 5× net worth
      - Track record = 5 years
      - Public offer = 25% for ₹800 Cr market cap (≤ ₹1600 Cr bucket)
      - Promoter post-issue holding = 75%, lock-in = 18 months
      - Post-issue paid-up capital = ₹15 Cr
      - Expected market cap = ₹800 Cr
      - Board: 6 directors, 3 independent, non-exec non-promoter chair
      - Audit committee: 4 members, 3 independent, chair is independent
      - No RPT issues, no auditor qualifications, no litigation

    Example::

        company = CompanyDataFactory.create()
        assert company.financials.years_of_operation == 5

        # Override a single field
        company = CompanyDataFactory.create(years_of_operation=2)
    """

    @classmethod
    def create(
        cls,
        *,
        # CompanyIdentification overrides
        company_name: str = "Acme Industries Pvt Ltd",
        cin: str = "L17110MH2000PLC019786",
        industry: str = "Manufacturing",
        incorporation_date: date = date(2000, 4, 1),
        registered_office: str = "Mumbai, Maharashtra",
        # FinancialHistory overrides
        fiscal_years: list[FiscalYear] | None = None,
        years_of_operation: int = 5,
        # Per-year operating profit (applied uniformly when fiscal_years not given)
        operating_profit: Decimal = Decimal("20"),
        net_tangible_assets: Decimal = Decimal("45"),
        monetary_assets: Decimal = Decimal("10"),
        net_worth: Decimal = Decimal("50"),
        # PromoterData overrides
        holding_percentage: Decimal = Decimal("75"),
        post_issue_holding: Decimal = Decimal("75"),
        lock_in_months: int = 18,
        is_capex_issue: bool = False,
        # GovernanceData overrides
        total_directors: int = 6,
        independent_directors: int = 3,
        is_chair_executive: bool = False,
        is_chair_promoter: bool = False,
        audit_total_members: int = 4,
        audit_independent_members: int = 3,
        audit_chair_is_independent: bool = True,
        # IssueDetails overrides
        issue_size: Decimal = Decimal("100"),
        pre_issue_net_worth: Decimal = Decimal("50"),
        post_issue_paid_up_capital: Decimal = Decimal("15"),
        expected_market_cap: Decimal = Decimal("800"),
        public_offer_percentage: Decimal = Decimal("25"),
        issue_type: str = "fresh",
        # LitigationData overrides
        has_criminal_cases: bool = False,
        total_litigation_exposure: Decimal = Decimal("0"),
        # RelatedPartyData overrides
        arm_length_certified: bool = True,
        total_rpt_value: Decimal = Decimal("2"),
        # AuditorData overrides
        auditor_name: str = "Deloitte Haskins & Sells LLP",
        has_qualifications: bool = False,
        has_modified_opinion: bool = False,
        years_as_auditor: int = 3,
    ) -> CompanyData:
        """Create a CompanyData instance with the given overrides.

        Any parameter not explicitly overridden defaults to a value that causes
        all rules to PASS. Override individual parameters to test specific rule
        failure scenarios.

        Args:
            company_name: Registered company name.
            cin: Corporate Identification Number.
            industry: Industry sector.
            incorporation_date: Date of incorporation.
            registered_office: Registered office address.
            fiscal_years: Complete list of FiscalYear objects. If provided,
                overrides all per-year financial defaults.
            years_of_operation: Total years the company has operated.
            operating_profit: Per-year operating profit applied to all FYs.
            net_tangible_assets: Per-year NTA applied to all FYs.
            monetary_assets: Per-year monetary assets applied to all FYs.
            net_worth: Per-year net worth applied to all FYs.
            holding_percentage: Promoter pre-issue holding percentage.
            post_issue_holding: Promoter post-issue holding percentage.
            lock_in_months: Promoter lock-in period in months.
            is_capex_issue: Whether the issue is for capital expenditure.
            total_directors: Total board directors.
            independent_directors: Independent directors on the board.
            is_chair_executive: Whether the chair is executive.
            is_chair_promoter: Whether the chair is a promoter.
            audit_total_members: Audit committee total members.
            audit_independent_members: Audit committee independent members.
            audit_chair_is_independent: Whether audit committee chair is independent.
            issue_size: Total issue size in ₹ Crores.
            pre_issue_net_worth: Net worth before the issue.
            post_issue_paid_up_capital: Post-issue paid-up capital.
            expected_market_cap: Expected market capitalisation.
            public_offer_percentage: Percentage offered to the public.
            issue_type: Type of issue (fresh/offer_for_sale/mixed).
            has_criminal_cases: Whether there are criminal cases pending.
            total_litigation_exposure: Total litigation exposure in ₹ Cr.
            arm_length_certified: Whether RPTs are certified at arm's length.
            total_rpt_value: Total RPT value in ₹ Cr.
            auditor_name: Name of the statutory auditor firm.
            has_qualifications: Whether audit report has qualifications.
            has_modified_opinion: Whether audit report has modified opinion.
            years_as_auditor: Years the current auditor has served.

        Returns:
            A fully constructed, immutable CompanyData instance.
        """
        identification = CompanyIdentification(
            company_name=company_name,
            cin=cin,
            industry=industry,
            incorporation_date=incorporation_date,
            registered_office=registered_office,
        )

        if fiscal_years is None:
            fiscal_years = [
                _make_fiscal_year(
                    label=f"FY{2020 + i}",
                    operating_profit=operating_profit,
                    net_tangible_assets=net_tangible_assets,
                    monetary_assets=monetary_assets,
                    net_worth=net_worth,
                )
                for i in range(5)
            ]

        financials = FinancialHistory(
            fiscal_years=fiscal_years,
            years_of_operation=years_of_operation,
        )

        promoter = PromoterData(
            holding_percentage=_ev(holding_percentage),
            post_issue_holding=_ev(post_issue_holding),
            lock_in_months=_ev(lock_in_months),
            is_capex_issue=is_capex_issue,
            entities=[
                PromoterEntity(
                    name="Test Promoter",
                    holding=holding_percentage,
                    pan=None,
                )
            ],
        )

        governance = GovernanceData(
            total_directors=_ev(total_directors),
            independent_directors=_ev(independent_directors),
            is_chair_executive=_ev(is_chair_executive),
            is_chair_promoter=_ev(is_chair_promoter),
            audit_committee=AuditCommittee(
                total_members=_ev(audit_total_members),
                independent_members=_ev(audit_independent_members),
                chair_is_independent=_ev(audit_chair_is_independent),
            ),
        )

        issue_details = IssueDetails(
            issue_size=_ev(issue_size),
            pre_issue_net_worth=_ev(pre_issue_net_worth),
            post_issue_paid_up_capital=_ev(post_issue_paid_up_capital),
            expected_market_cap=_ev(expected_market_cap),
            public_offer_percentage=_ev(public_offer_percentage),
            issue_type=issue_type,
        )

        litigation = LitigationData(
            pending_cases=[],
            total_exposure=_ev(total_litigation_exposure),
            has_criminal_cases=_ev(has_criminal_cases),
        )

        rpt = RelatedPartyData(
            transactions=[
                RPTTransaction(
                    party_name="Acme Holdings",
                    relationship="subsidiary",
                    transaction_type="loan",
                    value=total_rpt_value,
                )
            ]
            if total_rpt_value > Decimal("0")
            else [],
            total_rpt_value=_ev(total_rpt_value),
            arm_length_certified=_ev(arm_length_certified),
        )

        auditor = AuditorData(
            auditor_name=auditor_name,
            has_qualifications=_ev(has_qualifications),
            has_modified_opinion=_ev(has_modified_opinion),
            years_as_auditor=_ev(years_as_auditor),
        )

        return CompanyData(
            identification=identification,
            financials=financials,
            promoter=promoter,
            governance=governance,
            litigation=litigation,
            rpt=rpt,
            issue_details=issue_details,
            auditor=auditor,
            ruleset_version=DEFAULT_RULESET_VERSION,
        )

    @classmethod
    def create_with_low_confidence_nta(cls) -> CompanyData:
        """Create a company with LOW confidence NTA data (no human confirmation).

        Useful for testing INCONCLUSIVE verdict paths in NTA and monetary
        asset rules.

        Returns:
            CompanyData with LOW-confidence net_tangible_assets.
        """
        fiscal_years = [
            _make_fiscal_year(
                label=f"FY{2022 + i}",
                confidence=ConfidenceLevel.LOW,
            )
            for i in range(3)
        ]
        return cls.create(fiscal_years=fiscal_years)

    @classmethod
    def create_not_eligible(cls) -> CompanyData:
        """Create a company that fails mandatory rules (not eligible for IPO).

        Fails AVG_OPERATING_PROFIT_15CR and NTA_3CR.

        Returns:
            CompanyData that will produce NOT_ELIGIBLE status.
        """
        return cls.create(
            operating_profit=Decimal("5"),
            net_tangible_assets=Decimal("1"),
        )

    @classmethod
    def create_needs_review(cls) -> CompanyData:
        """Create a company with LOW confidence data (needs review).

        All data has LOW confidence, so most rules return INCONCLUSIVE.

        Returns:
            CompanyData that will produce NEEDS_REVIEW status.
        """
        return cls.create_with_low_confidence_nta()
