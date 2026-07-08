"""
backend/app/models/company_data.py

CompanyData canonical schema — the central data contract of the system.

CompanyData is the single object passed to the Rules Engine. It knows
nothing about PDFs, JSON, databases, or any input source. It is a pure,
validated, immutable data structure that encodes everything the Rules
Engine needs to produce an eligibility verdict.

This module MUST NOT import from:
  - app.rules, app.parser, app.api, app.engine, app.services

All financial values are wrapped in ExtractedValue[Decimal] to carry
provenance metadata. All models are frozen (immutable) after construction.

Regulation references encoded here:
  - SEBI (ICDR) Regulations, 2018
  - LODR Regulations, 2015
  - Companies Act, 2013
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.extracted_value import ExtractedValue
from app.models.ruleset_version import DEFAULT_RULESET_VERSION, RulesetVersion

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

_CIN_PATTERN = re.compile(
    r"^[A-Z]{1}[0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$"
)
_PERCENTAGE_MIN = Decimal("0")
_PERCENTAGE_MAX = Decimal("100")


# ---------------------------------------------------------------------------
# Sub-models: Company Identification
# ---------------------------------------------------------------------------


class CompanyIdentification(BaseModel):
    """Core identity fields for the company being evaluated.

    Used by the TrackRecord rule to derive years of operation from the
    incorporation date, and for labelling reports.

    Attributes:
        company_name: Registered company name, e.g., "Acme Widgets Pvt Ltd".
        cin: Corporate Identification Number (21-character alphanumeric).
            Format: L/U + 5 digits + 2 letters + 4 digits + 3 letters + 6 digits.
        industry: Industry sector, e.g., "Manufacturing — Engineering Goods".
        incorporation_date: Date of incorporation as registered with MCA.
        registered_office: Address of the registered office.

    Example:
        >>> from datetime import date
        >>> ident = CompanyIdentification(
        ...     company_name="Acme Widgets Pvt Ltd",
        ...     cin="L17110MH1973PLC019786",
        ...     industry="Manufacturing",
        ...     incorporation_date=date(2000, 4, 1),
        ...     registered_office="Mumbai, Maharashtra",
        ... )
        >>> ident.company_name
        'Acme Widgets Pvt Ltd'
    """

    model_config = ConfigDict(frozen=True)

    company_name: str
    cin: str
    industry: str
    incorporation_date: date
    registered_office: str

    @field_validator("cin")
    @classmethod
    def validate_cin_format(cls, value: str) -> str:
        """Validate that CIN matches the MCA-prescribed format.

        Args:
            value: The CIN string to validate.

        Returns:
            The validated CIN string.

        Raises:
            ValueError: If the CIN does not match the expected format.
        """
        if not _CIN_PATTERN.match(value):
            raise ValueError(
                f"Invalid CIN format: '{value}'. "
                "Expected format: L/U + 5 digits + 2 letters + 4 digits "
                "+ 3 letters + 6 digits (e.g., L17110MH1973PLC019786)."
            )
        return value


# ---------------------------------------------------------------------------
# Sub-models: Financial History
# ---------------------------------------------------------------------------


class FiscalYear(BaseModel):
    """Financial data for a single fiscal year.

    All numeric fields are wrapped in ExtractedValue[Decimal] to carry
    full provenance metadata. Financial values are in Indian Rupees (₹)
    in Crore units unless stated otherwise in the source document.

    Used by profitability, net worth, NTA, and other financial rules.

    Attributes:
        year_label: Human-readable FY label, e.g., "FY2024" or "FY2023-24".
        revenue: Total revenue from operations.
        operating_profit: Pre-tax operating profit (EBIT).
        pat: Profit after tax.
        net_worth: Total equity (paid-up capital + reserves and surplus).
        net_tangible_assets: Total assets minus intangible assets and
            current liabilities.
        monetary_assets: Cash and near-cash (cash + FDs + bank balances).
        total_assets: Total of all assets on the balance sheet.
        total_liabilities: Total of all liabilities.
        paid_up_capital: Paid-up share capital.
        reserves_and_surplus: Accumulated reserves and surplus.
        ebitda: Earnings before interest, taxes, depreciation, amortization.

    Example:
        >>> from decimal import Decimal
        >>> from app.models.enums import ConfidenceLevel, ExtractionMethod
        >>> ev = lambda v: ExtractedValue(
        ...     value=Decimal(v), source_document="AR.pdf",
        ...     extraction_method=ExtractionMethod.PDF_TABLE,
        ...     confidence=ConfidenceLevel.HIGH,
        ... )
        >>> fy = FiscalYear(
        ...     year_label="FY2024",
        ...     revenue=ev("100.0"),
        ...     operating_profit=ev("18.4"),
        ...     pat=ev("12.0"),
        ...     net_worth=ev("50.0"),
        ...     net_tangible_assets=ev("45.0"),
        ...     monetary_assets=ev("10.0"),
        ...     total_assets=ev("120.0"),
        ...     total_liabilities=ev("70.0"),
        ...     paid_up_capital=ev("10.0"),
        ...     reserves_and_surplus=ev("40.0"),
        ...     ebitda=ev("20.0"),
        ... )
        >>> fy.year_label
        'FY2024'
    """

    model_config = ConfigDict(frozen=True)

    year_label: str
    revenue: ExtractedValue[Decimal]
    operating_profit: ExtractedValue[Decimal]
    pat: ExtractedValue[Decimal]
    net_worth: ExtractedValue[Decimal]
    net_tangible_assets: ExtractedValue[Decimal]
    monetary_assets: ExtractedValue[Decimal]
    total_assets: ExtractedValue[Decimal]
    total_liabilities: ExtractedValue[Decimal]
    paid_up_capital: ExtractedValue[Decimal]
    reserves_and_surplus: ExtractedValue[Decimal]
    ebitda: ExtractedValue[Decimal]


class FinancialHistory(BaseModel):
    """Container for the company's multi-year financial record.

    The Rules Engine requires at least 3 fiscal years for most financial
    rules. Fiscal years must be stored in chronological order (oldest first).

    Attributes:
        fiscal_years: List of FiscalYear instances, ordered from oldest to
            most recent. Must contain at least one entry.
        years_of_operation: Total years the company has been operating.
            May differ from len(fiscal_years) if early years lack audited data.

    Example:
        >>> # See FiscalYear example for constructing individual years
        >>> history = FinancialHistory(
        ...     fiscal_years=[...],  # list of FiscalYear
        ...     years_of_operation=5,
        ... )
    """

    model_config = ConfigDict(frozen=True)

    fiscal_years: list[FiscalYear]
    years_of_operation: int

    @field_validator("fiscal_years")
    @classmethod
    def validate_chronological_order(
        cls, fiscal_years: list[FiscalYear]
    ) -> list[FiscalYear]:
        """Enforce chronological ordering of fiscal years (oldest first).

        Year labels must be unique and must be provided in ascending
        chronological order. The rule uses string comparison of year labels,
        which works for both "FY2022" and "FY2021-22" style labels when
        consistently formatted.

        Args:
            fiscal_years: The list of fiscal years to validate.

        Returns:
            The validated list, unchanged.

        Raises:
            ValueError: If fiscal year labels are not in ascending order
                or contain duplicates.
        """
        labels = [fy.year_label for fy in fiscal_years]
        if labels != sorted(set(labels)):
            raise ValueError(
                "fiscal_years must be in chronological order (oldest first) "
                f"with unique labels. Received: {labels}"
            )
        return fiscal_years


# ---------------------------------------------------------------------------
# Sub-models: Promoter
# ---------------------------------------------------------------------------


class PromoterEntity(BaseModel):
    """Individual promoter or promoter group entity.

    Attributes:
        name: Full legal name of the promoter entity.
        holding: Shareholding percentage held by this entity (0–100).
        pan: Permanent Account Number, if available.

    Example:
        >>> entity = PromoterEntity(
        ...     name="Rajesh Kumar", holding=Decimal("35.0"), pan="ABCDE1234F"
        ... )
    """

    model_config = ConfigDict(frozen=True)

    name: str
    holding: Decimal
    pan: str | None = None

    @field_validator("holding")
    @classmethod
    def validate_holding_range(cls, value: Decimal) -> Decimal:
        """Validate holding is between 0 and 100 percent.

        Args:
            value: The holding percentage to validate.

        Returns:
            The validated holding percentage.

        Raises:
            ValueError: If value is outside the 0–100 range.
        """
        if not (_PERCENTAGE_MIN <= value <= _PERCENTAGE_MAX):
            raise ValueError(
                f"PromoterEntity.holding must be between 0 and 100, got {value}."
            )
        return value


class PromoterData(BaseModel):
    """Promoter shareholding and lock-in information.

    Used by PROMOTER_CONTRIBUTION_20 and PROMOTER_LOCK_IN rules.

    Attributes:
        holding_percentage: Aggregate promoter holding as a percentage of
            pre-issue paid-up capital.
        post_issue_holding: Aggregate promoter holding post-IPO as a
            percentage of total post-issue capital.
        lock_in_months: Committed lock-in period in months.
            Standard: 18 months. Capex issues: 36 months (3 years).
        is_capex_issue: True if the issue proceeds are predominantly for
            capital expenditure. Affects the lock-in period requirement.
        entities: List of individual promoter entities and their holdings.

    Example:
        >>> from decimal import Decimal
        >>> from app.models.enums import ConfidenceLevel, ExtractionMethod
        >>> ev = lambda v, T=Decimal: ExtractedValue(
        ...     value=T(v), source_document="DRHP.pdf",
        ...     extraction_method=ExtractionMethod.MANUAL,
        ...     confidence=ConfidenceLevel.HIGH,
        ... )
        >>> pd = PromoterData(
        ...     holding_percentage=ev("55.0"),
        ...     post_issue_holding=ev("45.0"),
        ...     lock_in_months=ev(18, int),
        ...     is_capex_issue=False,
        ...     entities=[],
        ... )
    """

    model_config = ConfigDict(frozen=True)

    holding_percentage: ExtractedValue[Decimal]
    post_issue_holding: ExtractedValue[Decimal]
    lock_in_months: ExtractedValue[int]
    is_capex_issue: bool
    entities: list[PromoterEntity]


# ---------------------------------------------------------------------------
# Sub-models: Governance
# ---------------------------------------------------------------------------


class AuditCommittee(BaseModel):
    """Audit Committee composition for LODR compliance.

    Used by the AUDIT_COMMITTEE advisory rule.

    Attributes:
        total_members: Total number of audit committee members.
        independent_members: Number of independent directors on the
            audit committee.
        chair_is_independent: Whether the audit committee chair is an
            independent director (required by LODR Reg. 18).

    Example:
        >>> from app.models.enums import ConfidenceLevel, ExtractionMethod
        >>> ev_int = lambda v: ExtractedValue(
        ...     value=v, source_document="AR.pdf",
        ...     extraction_method=ExtractionMethod.MANUAL,
        ...     confidence=ConfidenceLevel.HIGH,
        ... )
        >>> ev_bool = lambda v: ExtractedValue(
        ...     value=v, source_document="AR.pdf",
        ...     extraction_method=ExtractionMethod.MANUAL,
        ...     confidence=ConfidenceLevel.HIGH,
        ... )
        >>> ac = AuditCommittee(
        ...     total_members=ev_int(4),
        ...     independent_members=ev_int(3),
        ...     chair_is_independent=ev_bool(True),
        ... )
    """

    model_config = ConfigDict(frozen=True)

    total_members: ExtractedValue[int]
    independent_members: ExtractedValue[int]
    chair_is_independent: ExtractedValue[bool]


class GovernanceData(BaseModel):
    """Board and governance structure for Companies Act / LODR compliance.

    Used by BOARD_INDEPENDENCE and AUDIT_COMMITTEE advisory rules.

    Attributes:
        total_directors: Total number of directors on the board.
        independent_directors: Number of independent directors.
        is_chair_executive: True if the board chairperson is an executive
            director (affects minimum independent director ratio).
        is_chair_promoter: True if the board chairperson is a promoter
            (also triggers the higher independence requirement).
        audit_committee: Audit Committee composition details.

    Example:
        >>> # See AuditCommittee example for construction details
    """

    model_config = ConfigDict(frozen=True)

    total_directors: ExtractedValue[int]
    independent_directors: ExtractedValue[int]
    is_chair_executive: ExtractedValue[bool]
    is_chair_promoter: ExtractedValue[bool]
    audit_committee: AuditCommittee


# ---------------------------------------------------------------------------
# Sub-models: Issue Details
# ---------------------------------------------------------------------------


_VALID_ISSUE_TYPES = frozenset({"fresh", "offer_for_sale", "mixed"})


class IssueDetails(BaseModel):
    """IPO-specific parameters for the proposed issue.

    Used by ISSUE_SIZE_5X, PUBLIC_OFFER_MIN, MIN_POST_ISSUE_CAPITAL, and
    MIN_MARKET_CAP rules.

    Attributes:
        issue_size: Total size of the issue in ₹ Crores.
        pre_issue_net_worth: Net worth before the issue proceeds, in ₹ Cr.
        post_issue_paid_up_capital: Paid-up capital after the issue, ₹ Cr.
        expected_market_cap: Expected market capitalisation at issue price,
            in ₹ Crores. Used for public float threshold selection.
        public_offer_percentage: Percentage of post-issue capital offered
            to the public (determines minimum float compliance).
        issue_type: Nature of the issue: "fresh", "offer_for_sale", or
            "mixed".

    Example:
        >>> from decimal import Decimal
        >>> from app.models.enums import ConfidenceLevel, ExtractionMethod
        >>> ev = lambda v: ExtractedValue(
        ...     value=Decimal(v), source_document="DRHP.pdf",
        ...     extraction_method=ExtractionMethod.MANUAL,
        ...     confidence=ConfidenceLevel.HIGH,
        ... )
        >>> details = IssueDetails(
        ...     issue_size=ev("100.0"),
        ...     pre_issue_net_worth=ev("50.0"),
        ...     post_issue_paid_up_capital=ev("20.0"),
        ...     expected_market_cap=ev("800.0"),
        ...     public_offer_percentage=ev("25.0"),
        ...     issue_type="fresh",
        ... )
    """

    model_config = ConfigDict(frozen=True)

    issue_size: ExtractedValue[Decimal]
    pre_issue_net_worth: ExtractedValue[Decimal]
    post_issue_paid_up_capital: ExtractedValue[Decimal]
    expected_market_cap: ExtractedValue[Decimal]
    public_offer_percentage: ExtractedValue[Decimal]
    issue_type: str

    @field_validator("issue_type")
    @classmethod
    def validate_issue_type(cls, value: str) -> str:
        """Validate issue type is a known value.

        Args:
            value: The issue type string to validate.

        Returns:
            The normalised lower-case issue type string.

        Raises:
            ValueError: If the issue type is not recognised.
        """
        normalised = value.lower().strip()
        if normalised not in _VALID_ISSUE_TYPES:
            raise ValueError(
                f"issue_type must be one of {sorted(_VALID_ISSUE_TYPES)}, "
                f"got '{value}'."
            )
        return normalised


# ---------------------------------------------------------------------------
# Sub-models: Litigation
# ---------------------------------------------------------------------------


class LitigationCase(BaseModel):
    """Individual pending litigation case.

    Attributes:
        case_type: Nature of the case, e.g., "civil", "criminal", "tax",
            "regulatory".
        description: Brief description of the matter.
        exposure: Estimated financial exposure in ₹ Crores.
        court: Court or tribunal where the case is pending.
        status: Current status, e.g., "pending", "under_appeal".

    Example:
        >>> from decimal import Decimal
        >>> case = LitigationCase(
        ...     case_type="tax",
        ...     description="Income tax demand FY2022",
        ...     exposure=Decimal("2.5"),
        ...     court="Income Tax Appellate Tribunal",
        ...     status="pending",
        ... )
    """

    model_config = ConfigDict(frozen=True)

    case_type: str
    description: str
    exposure: Decimal
    court: str
    status: str


class LitigationData(BaseModel):
    """Aggregated litigation information.

    Used by the LITIGATION_RISK advisory rule.

    Attributes:
        pending_cases: List of all pending litigation cases.
        total_exposure: Total financial exposure across all pending cases,
            in ₹ Crores.
        has_criminal_cases: True if any pending case is criminal in nature.
            Criminal cases are flagged separately as a higher-risk signal.

    Example:
        >>> # See LitigationCase example for construction
    """

    model_config = ConfigDict(frozen=True)

    pending_cases: list[LitigationCase]
    total_exposure: ExtractedValue[Decimal]
    has_criminal_cases: ExtractedValue[bool]


# ---------------------------------------------------------------------------
# Sub-models: Related Party Transactions
# ---------------------------------------------------------------------------


class RPTTransaction(BaseModel):
    """Individual related party transaction.

    Attributes:
        party_name: Name of the related party.
        relationship: Nature of the relationship, e.g., "subsidiary",
            "key_management_personnel", "director_relative".
        transaction_type: Type of transaction, e.g., "loan", "purchase",
            "sale", "guarantee".
        value: Transaction value in ₹ Crores.

    Example:
        >>> from decimal import Decimal
        >>> txn = RPTTransaction(
        ...     party_name="Acme Holdings Pvt Ltd",
        ...     relationship="subsidiary",
        ...     transaction_type="loan",
        ...     value=Decimal("5.0"),
        ... )
    """

    model_config = ConfigDict(frozen=True)

    party_name: str
    relationship: str
    transaction_type: str
    value: Decimal


class RelatedPartyData(BaseModel):
    """Related party transaction summary.

    Used by the RPT_DISCLOSURE advisory rule.

    Attributes:
        transactions: List of individual related party transactions.
        total_rpt_value: Aggregate value of all related party transactions,
            in ₹ Crores.
        arm_length_certified: True if all RPTs have been certified as being
            on arm's length terms by the audit committee.

    Example:
        >>> # See RPTTransaction example for construction
    """

    model_config = ConfigDict(frozen=True)

    transactions: list[RPTTransaction]
    total_rpt_value: ExtractedValue[Decimal]
    arm_length_certified: ExtractedValue[bool]


# ---------------------------------------------------------------------------
# Sub-models: Auditor
# ---------------------------------------------------------------------------


class AuditorData(BaseModel):
    """Statutory auditor information.

    Used by the AUDITOR_QUALIFICATION advisory rule.

    Attributes:
        auditor_name: Name of the statutory auditor firm.
        has_qualifications: True if the auditor's report contains
            qualifications or emphasis of matter paragraphs.
        has_modified_opinion: True if the auditor expressed a modified
            opinion (qualified, adverse, or disclaimer).
        years_as_auditor: Number of consecutive years this firm has been
            the statutory auditor. Relevant for auditor independence.

    Example:
        >>> from app.models.enums import ConfidenceLevel, ExtractionMethod
        >>> ev = lambda v, T=bool: ExtractedValue(
        ...     value=T(v), source_document="AR.pdf",
        ...     extraction_method=ExtractionMethod.MANUAL,
        ...     confidence=ConfidenceLevel.HIGH,
        ... )
        >>> auditor = AuditorData(
        ...     auditor_name="Deloitte Haskins & Sells LLP",
        ...     has_qualifications=ev(False),
        ...     has_modified_opinion=ev(False),
        ...     years_as_auditor=ExtractedValue(
        ...         value=3, source_document="AR.pdf",
        ...         extraction_method=ExtractionMethod.MANUAL,
        ...         confidence=ConfidenceLevel.HIGH,
        ...     ),
        ... )
    """

    model_config = ConfigDict(frozen=True)

    auditor_name: str
    has_qualifications: ExtractedValue[bool]
    has_modified_opinion: ExtractedValue[bool]
    years_as_auditor: ExtractedValue[int]


# ---------------------------------------------------------------------------
# Root model: CompanyData
# ---------------------------------------------------------------------------


class CompanyData(BaseModel):
    """Canonical company schema — the single input to the Rules Engine.

    CompanyData is the central data contract of the entire system. It is
    the only argument accepted by BaseRule.evaluate(). It carries all
    financial, governance, promoter, litigation, and issue information
    required to evaluate every mandatory and advisory rule.

    After construction, CompanyData is immutable (frozen=True). This
    guarantees that the Rules Engine always operates on a consistent,
    unmodified snapshot of the company's data.

    The model is input-source agnostic: the same object is constructed
    whether data came from a PDF, a manual JSON entry, or an API
    integration. The Rules Engine knows nothing about how data was obtained.

    Attributes:
        identification: Company identity (name, CIN, sector, incorporation).
        financials: Multi-year financial history (revenue, profit, net worth).
        promoter: Promoter shareholding structure and lock-in.
        governance: Board composition and audit committee.
        litigation: Pending litigation cases and exposure.
        rpt: Related party transaction summary.
        issue_details: Proposed IPO structure (size, float, market cap).
        auditor: Statutory auditor information.
        ruleset_version: Version of the ruleset used to evaluate this data.

    Example:
        >>> # Use CompanyDataFactory in tests instead of constructing directly.
        >>> # For production code, the Extraction Service constructs this.
        >>> company = CompanyData(
        ...     identification=...,
        ...     financials=...,
        ...     promoter=...,
        ...     governance=...,
        ...     litigation=...,
        ...     rpt=...,
        ...     issue_details=...,
        ...     auditor=...,
        ...     ruleset_version=DEFAULT_RULESET_VERSION,
        ... )
    """

    model_config = ConfigDict(frozen=True)

    identification: CompanyIdentification
    financials: FinancialHistory
    promoter: PromoterData
    governance: GovernanceData
    litigation: LitigationData
    rpt: RelatedPartyData
    issue_details: IssueDetails
    auditor: AuditorData
    ruleset_version: RulesetVersion = DEFAULT_RULESET_VERSION
