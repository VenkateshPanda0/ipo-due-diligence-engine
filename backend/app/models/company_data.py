"""
backend/app/models/company_data.py

Canonical ``CompanyData`` schema — the single input to the rules engine.

Design rules:
  * Every fact used by a rule is an ``ExtractedValue`` (value + provenance).
  * Every fact is optional. ``None`` means "no evidence", which rules report as
    INCONCLUSIVE — never as a regulatory failure, and never fabricated.
  * Monetary values are Decimal ₹ crore; percentages are 0–100.
  * Models are frozen; corrections create new snapshots.

The schema is backward compatible with v1 JSON payloads: every v1 field keeps its
name and type; new fields are optional with neutral defaults.

This module MUST NOT import from app.rules, app.intelligence, app.api, app.engine.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ListingRoute, StatementBasis
from app.models.extracted_value import ExtractedValue
from app.models.field_paths import period_sort_key
from app.models.ruleset_version import DEFAULT_RULESET_VERSION, RulesetVersion

_CIN_PATTERN = re.compile(r"^[A-Z]{1}[0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
_PERCENTAGE_MIN = Decimal("0")
_PERCENTAGE_MAX = Decimal("100")
_VALID_ISSUE_TYPES = frozenset({"fresh", "offer_for_sale", "mixed"})

EVDecimal = ExtractedValue[Decimal]
EVInt = ExtractedValue[int]
EVBool = ExtractedValue[bool]


def _check_percentage(ev: EVDecimal | None, name: str) -> None:
    if ev is not None and not (_PERCENTAGE_MIN <= ev.value <= _PERCENTAGE_MAX):
        raise ValueError(f"{name} must be between 0 and 100, got {ev.value}.")


class CompanyIdentification(BaseModel):
    """Company identity. Only ``company_name`` is required."""

    model_config = ConfigDict(frozen=True)

    company_name: str = Field(min_length=1, max_length=300)
    cin: str | None = None
    industry: str | None = None
    incorporation_date: date | None = None
    registered_office: str | None = None

    @field_validator("cin")
    @classmethod
    def validate_cin_format(cls, value: str | None) -> str | None:
        """Validate MCA CIN format: L/U + 5 digits + 2 letters + 4 digits + 3 letters + 6 digits."""
        if value is None:
            return None
        value = value.strip().upper()
        if not _CIN_PATTERN.match(value):
            raise ValueError(
                f"Invalid CIN format: '{value}'. Expected format: L/U + 5 digits + 2 letters "
                "+ 4 digits + 3 letters + 6 digits."
            )
        return value


class FiscalYear(BaseModel):
    """One reporting period of restated financial information (₹ crore).

    ``operating_profit`` is the ICDR Reg 6(1)(b) operating profit as reported in
    the offer document's restated statements — not PBT or EBIT by assumption.
    ``months`` supports the "full year of twelve months" requirement.
    """

    model_config = ConfigDict(frozen=True)

    year_label: str = Field(min_length=1, max_length=40)
    period_end: date | None = None
    months: int = Field(default=12, ge=1, le=24)
    revenue: EVDecimal | None = None
    operating_profit: EVDecimal | None = None
    pat: EVDecimal | None = None
    net_worth: EVDecimal | None = None
    net_tangible_assets: EVDecimal | None = None
    monetary_assets: EVDecimal | None = None
    total_assets: EVDecimal | None = None
    total_liabilities: EVDecimal | None = None
    paid_up_capital: EVDecimal | None = None
    reserves_and_surplus: EVDecimal | None = None
    ebitda: EVDecimal | None = None


class FinancialHistory(BaseModel):
    """Multi-year financial history, ordered oldest first."""

    model_config = ConfigDict(frozen=True)

    fiscal_years: list[FiscalYear] = Field(default_factory=list)
    years_of_operation: int | None = Field(default=None, ge=0)
    statement_basis: StatementBasis = StatementBasis.UNKNOWN
    is_restated: bool | None = None

    @field_validator("fiscal_years")
    @classmethod
    def validate_chronological_order(cls, fiscal_years: list[FiscalYear]) -> list[FiscalYear]:
        """Require unique, chronologically ordered periods (oldest first)."""
        labels = [fy.year_label for fy in fiscal_years]
        if len(set(labels)) != len(labels):
            raise ValueError(f"fiscal_years must have unique labels. Received: {labels}")
        keys = [period_sort_key(fy.year_label, fy.period_end) for fy in fiscal_years]
        if keys != sorted(keys):
            raise ValueError(
                f"fiscal_years must be in chronological order (oldest first). Received: {labels}"
            )
        return fiscal_years


class PromoterEntity(BaseModel):
    """An individual promoter entity and its holding percentage."""

    model_config = ConfigDict(frozen=True)

    name: str
    holding: Decimal
    pan: str | None = None

    @field_validator("holding")
    @classmethod
    def validate_holding_range(cls, value: Decimal) -> Decimal:
        """Holding must be a percentage between 0 and 100."""
        if not (_PERCENTAGE_MIN <= value <= _PERCENTAGE_MAX):
            raise ValueError(f"Promoter holding must be between 0 and 100, got {value}.")
        return value


class PromoterData(BaseModel):
    """Promoter shareholding, contribution and lock-in (ICDR Reg 14, 16).

    Attributes:
        holding_percentage: Pre-issue promoter holding (%).
        post_issue_holding: Post-issue promoter holding (% of post-issue capital,
            computed on the expanded capital per Reg 14 Explanation (I)).
        eligible_non_promoter_contribution: % of post-issue capital contributed
            by entities permitted under the Reg 14(1) proviso (max 10 counts).
        lock_in_months: Lock-in committed for the minimum promoters' contribution.
        is_capex_issue: Majority of fresh-issue proceeds for capital expenditure
            (Reg 16(1)(a) proviso). ``None`` = not determined.
        has_identifiable_promoter: False only if the issuer has no identifiable
            promoter (Reg 14(1) second proviso).
    """

    model_config = ConfigDict(frozen=True)

    holding_percentage: EVDecimal | None = None
    post_issue_holding: EVDecimal | None = None
    eligible_non_promoter_contribution: EVDecimal | None = None
    lock_in_months: EVInt | None = None
    is_capex_issue: bool | None = None
    has_identifiable_promoter: bool = True
    entities: list[PromoterEntity] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_percentages(self) -> PromoterData:
        _check_percentage(self.holding_percentage, "holding_percentage")
        _check_percentage(self.post_issue_holding, "post_issue_holding")
        _check_percentage(
            self.eligible_non_promoter_contribution, "eligible_non_promoter_contribution"
        )
        return self


class AuditCommittee(BaseModel):
    """Audit committee composition (LODR Reg 18(1))."""

    model_config = ConfigDict(frozen=True)

    total_members: EVInt | None = None
    independent_members: EVInt | None = None
    chair_is_independent: EVBool | None = None


class GovernanceData(BaseModel):
    """Board composition (LODR Reg 17(1))."""

    model_config = ConfigDict(frozen=True)

    total_directors: EVInt | None = None
    independent_directors: EVInt | None = None
    is_chair_executive: EVBool | None = None
    is_chair_promoter: EVBool | None = None
    audit_committee: AuditCommittee = Field(default_factory=AuditCommittee)

    @model_validator(mode="after")
    def validate_independent_le_total(self) -> GovernanceData:
        if (
            self.total_directors is not None
            and self.independent_directors is not None
            and self.independent_directors.value > self.total_directors.value
        ):
            raise ValueError("independent_directors cannot exceed total_directors.")
        return self


class IssueDetails(BaseModel):
    """Proposed issue structure. Monetary values in ₹ crore.

    Attributes:
        listing_route: Declared IPO route. Defaults to main board Reg 6(1).
        issue_size: Total issue size (fresh issue + offer for sale).
        pre_issue_net_worth: Retained for v1 compatibility (not used by 2.0.0).
        post_issue_paid_up_capital: Post-issue paid-up equity capital (face value).
        expected_market_cap: Post-issue capital at the offer price ("market value"
            used by SCRR Rule 19(2)(b)).
        public_offer_percentage: Offer to the public as % of post-issue capital.
        issue_type: "fresh", "offer_for_sale" or "mixed".
        is_book_built: Issue made through the book-building process (Reg 6(2)).
        qib_net_offer_allocation: % of net offer the issuer undertakes to allot to
            QIBs (Reg 6(2) requires at least 75).
        refund_undertaking: Issuer undertakes to refund if the QIB allotment
            condition fails (Reg 6(2)).
        excess_monetary_assets_committed: Issuer has utilised / firmly committed
            to utilise monetary assets above 50 % of NTA (Reg 6(1)(a) first proviso).
    """

    model_config = ConfigDict(frozen=True)

    listing_route: ListingRoute = ListingRoute.MAINBOARD_REG6_1
    issue_size: EVDecimal | None = None
    pre_issue_net_worth: EVDecimal | None = None
    post_issue_paid_up_capital: EVDecimal | None = None
    expected_market_cap: EVDecimal | None = None
    public_offer_percentage: EVDecimal | None = None
    issue_type: str = "fresh"
    is_book_built: bool | None = None
    qib_net_offer_allocation: EVDecimal | None = None
    refund_undertaking: bool | None = None
    excess_monetary_assets_committed: bool | None = None

    @field_validator("issue_type")
    @classmethod
    def validate_issue_type(cls, value: str) -> str:
        normalised = value.lower().strip()
        if normalised not in _VALID_ISSUE_TYPES:
            raise ValueError(
                f"issue_type must be one of {sorted(_VALID_ISSUE_TYPES)}, got '{value}'."
            )
        return normalised

    @model_validator(mode="after")
    def validate_percentages(self) -> IssueDetails:
        _check_percentage(self.public_offer_percentage, "public_offer_percentage")
        _check_percentage(self.qib_net_offer_allocation, "qib_net_offer_allocation")
        return self


class EligibilityDeclarations(BaseModel):
    """Facts for ICDR Reg 5 (ineligible entities) and Reg 6(1)(d) (name change).

    Each item is ``None`` until evidenced; ``True`` indicates the disqualifying
    condition exists.
    """

    model_config = ConfigDict(frozen=True)

    debarred_by_sebi: EVBool | None = None
    promoter_or_director_of_debarred_company: EVBool | None = None
    wilful_defaulter_or_fraudulent_borrower: EVBool | None = None
    fugitive_economic_offender: EVBool | None = None
    outstanding_convertibles_not_exempt: EVBool | None = None
    name_changed_within_last_year: EVBool | None = None
    revenue_pct_from_new_name_activity: EVDecimal | None = None

    @model_validator(mode="after")
    def validate_percentages(self) -> EligibilityDeclarations:
        _check_percentage(
            self.revenue_pct_from_new_name_activity, "revenue_pct_from_new_name_activity"
        )
        return self


class LitigationCase(BaseModel):
    """A pending litigation matter. ``exposure`` in ₹ crore."""

    model_config = ConfigDict(frozen=True)

    case_type: str
    description: str
    exposure: Decimal
    court: str
    status: str


class LitigationData(BaseModel):
    """Pending litigation summary."""

    model_config = ConfigDict(frozen=True)

    pending_cases: list[LitigationCase] = Field(default_factory=list)
    total_exposure: EVDecimal | None = None
    has_criminal_cases: EVBool | None = None


class RPTTransaction(BaseModel):
    """A related party transaction. ``value`` in ₹ crore."""

    model_config = ConfigDict(frozen=True)

    party_name: str
    relationship: str
    transaction_type: str
    value: Decimal


class RelatedPartyData(BaseModel):
    """Related party transaction summary."""

    model_config = ConfigDict(frozen=True)

    transactions: list[RPTTransaction] = Field(default_factory=list)
    total_rpt_value: EVDecimal | None = None
    arm_length_certified: EVBool | None = None


class AuditorData(BaseModel):
    """Statutory auditor information."""

    model_config = ConfigDict(frozen=True)

    auditor_name: str | None = None
    has_qualifications: EVBool | None = None
    has_modified_opinion: EVBool | None = None
    years_as_auditor: EVInt | None = None


class CompanyData(BaseModel):
    """Canonical company schema — the only argument to ``BaseRule.evaluate``.

    ``ruleset_version`` is retained for v1 payload compatibility only; the ruleset
    actually applied is recorded on the report by the decision engine.
    """

    model_config = ConfigDict(frozen=True)

    identification: CompanyIdentification
    financials: FinancialHistory = Field(default_factory=FinancialHistory)
    promoter: PromoterData = Field(default_factory=PromoterData)
    governance: GovernanceData = Field(default_factory=GovernanceData)
    litigation: LitigationData = Field(default_factory=LitigationData)
    rpt: RelatedPartyData = Field(default_factory=RelatedPartyData)
    issue_details: IssueDetails = Field(default_factory=IssueDetails)
    auditor: AuditorData = Field(default_factory=AuditorData)
    declarations: EligibilityDeclarations = Field(default_factory=EligibilityDeclarations)
    ruleset_version: RulesetVersion = DEFAULT_RULESET_VERSION
