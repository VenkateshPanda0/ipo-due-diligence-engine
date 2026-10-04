"""Self-contained structured extraction boundary.

The extractor is deliberately local and deterministic: label/table pattern
extraction from pdfplumber text and table context. It never calls a cloud LLM or
external network service.

Security: structured payloads embedded in document text (e.g. a JSON block) are
NOT trusted. Ruleset 1.0.0 accepted a ``BEGIN_COMPANY_DATA_JSON`` block, which let
any uploaded PDF dictate its own values, confidence and human-confirmation flags
(baseline defect D8). That path has been removed.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

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
)
from app.models.enums import ConfidenceLevel, ExtractionMethod
from app.models.exceptions import ExtractionError
from app.models.extracted_value import ExtractedValue
from app.models.ruleset_version import DEFAULT_RULESET_VERSION

_NUMBER_PATTERN = r"[-+]?\d[\d,]*(?:\.\d+)?"

_FIELD_LABELS = {
    "revenue": ("revenue", "revenue from operations", "total revenue"),
    "operating_profit": ("operating profit", "profit before tax", "ebit"),
    "pat": ("pat", "profit after tax", "profit for the year"),
    "net_worth": ("net worth", "shareholders funds", "shareholder funds"),
    "net_tangible_assets": ("net tangible assets", "tangible net worth", "nta"),
    "monetary_assets": ("monetary assets", "cash and bank balances", "cash equivalents"),
    "total_assets": ("total assets",),
    "total_liabilities": ("total liabilities",),
    "paid_up_capital": ("paid-up capital", "paid up capital", "share capital"),
    "reserves_and_surplus": ("reserves and surplus", "other equity", "reserves"),
    "ebitda": ("ebitda",),
}


class AIExtractor:
    """Extract CompanyData from document text without cloud dependencies."""

    def extract_company_data(self, text: str) -> CompanyData:
        """Extract CompanyData from local label patterns."""
        return _LocalPatternExtractor(text).extract()


class _LocalPatternExtractor:
    """Deterministic label and table extractor for common IPO documents."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._normalized = text.replace("\r\n", "\n")

    def extract(self) -> CompanyData:
        fiscal_years = self._extract_fiscal_years()
        issue_size = self._decimal_label("issue_size", ("issue size", "fresh issue size"))
        public_offer = self._decimal_label(
            "public_offer_percentage",
            ("public offer percentage", "public offer", "offer to public"),
        )
        expected_market_cap = self._decimal_label(
            "expected_market_cap",
            ("expected market cap", "market capitalisation", "market capitalization"),
        )

        return CompanyData(
            identification=CompanyIdentification(
                company_name=self._string_label("company_name", ("company name", "issuer")),
                cin=self._string_label("cin", ("cin", "corporate identification number")),
                industry=self._string_label("industry", ("industry", "sector")),
                incorporation_date=self._date_label(
                    "incorporation_date",
                    ("incorporation date", "date of incorporation"),
                ),
                registered_office=self._string_label(
                    "registered_office",
                    ("registered office", "registered office address"),
                ),
            ),
            financials=FinancialHistory(
                fiscal_years=fiscal_years,
                years_of_operation=self._int_label(
                    "years_of_operation",
                    ("years of operation", "operating history"),
                ),
            ),
            promoter=PromoterData(
                holding_percentage=self._ev_decimal(
                    self._decimal_label("holding_percentage", ("promoter holding",)),
                    "promoter holding",
                ),
                post_issue_holding=self._ev_decimal(
                    self._decimal_label(
                        "post_issue_holding",
                        ("post issue promoter holding", "post-issue promoter holding"),
                    ),
                    "post issue promoter holding",
                ),
                lock_in_months=self._ev_int(
                    self._int_label("lock_in_months", ("lock in months", "lock-in months")),
                    "lock in months",
                ),
                is_capex_issue=self._bool_label("is_capex_issue", ("capex issue",)),
                entities=[
                    PromoterEntity(
                        name=self._string_label("promoter_name", ("promoter name",)),
                        holding=self._decimal_label("holding_percentage", ("promoter holding",)),
                    )
                ],
            ),
            governance=GovernanceData(
                total_directors=self._ev_int(
                    self._int_label("total_directors", ("total directors",)),
                    "total directors",
                ),
                independent_directors=self._ev_int(
                    self._int_label("independent_directors", ("independent directors",)),
                    "independent directors",
                ),
                is_chair_executive=self._ev_bool(
                    self._bool_label("is_chair_executive", ("chair executive",)),
                    "chair executive",
                ),
                is_chair_promoter=self._ev_bool(
                    self._bool_label("is_chair_promoter", ("chair promoter",)),
                    "chair promoter",
                ),
                audit_committee=AuditCommittee(
                    total_members=self._ev_int(
                        self._int_label("audit_total_members", ("audit committee members",)),
                        "audit committee members",
                    ),
                    independent_members=self._ev_int(
                        self._int_label(
                            "audit_independent_members",
                            ("audit independent members",),
                        ),
                        "audit independent members",
                    ),
                    chair_is_independent=self._ev_bool(
                        self._bool_label(
                            "audit_chair_is_independent",
                            ("audit chair independent",),
                        ),
                        "audit chair independent",
                    ),
                ),
            ),
            litigation=LitigationData(
                pending_cases=[],
                total_exposure=self._ev_decimal(
                    self._decimal_label("total_litigation_exposure", ("litigation exposure",)),
                    "litigation exposure",
                ),
                has_criminal_cases=self._ev_bool(
                    self._bool_label("has_criminal_cases", ("criminal cases",)),
                    "criminal cases",
                ),
            ),
            rpt=RelatedPartyData(
                transactions=[],
                total_rpt_value=self._ev_decimal(
                    self._decimal_label("total_rpt_value", ("related party transaction value",)),
                    "related party transaction value",
                ),
                arm_length_certified=self._ev_bool(
                    self._bool_label("arm_length_certified", ("arm length certified",)),
                    "arm length certified",
                ),
            ),
            issue_details=IssueDetails(
                issue_size=self._ev_decimal(issue_size, "issue size"),
                pre_issue_net_worth=None,  # never derived; v1 copied latest net worth (fabrication)
                post_issue_paid_up_capital=self._ev_decimal(
                    self._decimal_label(
                        "post_issue_paid_up_capital",
                        ("post issue paid up capital", "post-issue paid-up capital"),
                    ),
                    "post issue paid up capital",
                ),
                expected_market_cap=self._ev_decimal(expected_market_cap, "expected market cap"),
                public_offer_percentage=self._ev_decimal(public_offer, "public offer"),
                issue_type=self._string_label("issue_type", ("issue type",)),
            ),
            auditor=AuditorData(
                auditor_name=self._string_label("auditor_name", ("auditor name",)),
                has_qualifications=self._ev_bool(
                    self._bool_label("has_qualifications", ("auditor qualifications",)),
                    "auditor qualifications",
                ),
                has_modified_opinion=self._ev_bool(
                    self._bool_label("has_modified_opinion", ("modified opinion",)),
                    "modified opinion",
                ),
                years_as_auditor=self._ev_int(
                    self._int_label("years_as_auditor", ("years as auditor",)),
                    "years as auditor",
                ),
            ),
            ruleset_version=DEFAULT_RULESET_VERSION,
        )

    def _extract_fiscal_years(self) -> list[FiscalYear]:
        rows = self._extract_pipe_rows()
        header_index = self._find_financial_header(rows)
        if header_index is None:
            raise ExtractionError("financials", "No financial table with fiscal-year rows found")
        header = [self._clean_cell(cell).lower() for cell in rows[header_index]]
        fiscal_years: list[FiscalYear] = []
        for row in rows[header_index + 1 :]:
            if not row or not re.search(r"fy\s*\d{4}|\d{4}\s*-\s*\d{2}", row[0], re.I):
                continue
            values = self._row_values(header, row)
            fiscal_years.append(
                FiscalYear(
                    year_label=self._clean_cell(row[0]).replace(" ", ""),
                    revenue=self._ev_decimal(values["revenue"], "revenue"),
                    operating_profit=self._ev_decimal(
                        values["operating_profit"], "operating profit"
                    ),
                    pat=self._ev_decimal(values["pat"], "pat"),
                    net_worth=self._ev_decimal(values["net_worth"], "net worth"),
                    net_tangible_assets=self._ev_decimal(
                        values["net_tangible_assets"], "net tangible assets"
                    ),
                    monetary_assets=self._ev_decimal(values["monetary_assets"], "monetary assets"),
                    total_assets=self._ev_decimal(values["total_assets"], "total assets"),
                    total_liabilities=self._ev_decimal(
                        values["total_liabilities"], "total liabilities"
                    ),
                    paid_up_capital=self._ev_decimal(values["paid_up_capital"], "paid up capital"),
                    reserves_and_surplus=self._ev_decimal(
                        values["reserves_and_surplus"], "reserves and surplus"
                    ),
                    ebitda=self._ev_decimal(values["ebitda"], "ebitda"),
                )
            )
        if not fiscal_years:
            raise ExtractionError("financials", "Financial table had no usable fiscal-year rows")
        return fiscal_years

    def _extract_pipe_rows(self) -> list[list[str]]:
        rows: list[list[str]] = []
        for line in self._normalized.splitlines():
            if line.count("|") >= 2:
                rows.append([self._clean_cell(cell) for cell in line.strip("|").split("|")])
        return rows

    def _find_financial_header(self, rows: list[list[str]]) -> int | None:
        for index, row in enumerate(rows):
            joined = " ".join(cell.lower() for cell in row)
            if "fy" in joined and "revenue" in joined and "net worth" in joined:
                return index
        return None

    def _row_values(self, header: list[str], row: list[str]) -> dict[str, Decimal]:
        values: dict[str, Decimal] = {}
        for field, labels in _FIELD_LABELS.items():
            column = self._find_column(header, labels)
            if column is None or column >= len(row):
                raise ExtractionError(field, f"No column found for {field}")
            values[field] = self._parse_decimal(row[column], field)
        return values

    @staticmethod
    def _find_column(header: list[str], labels: tuple[str, ...]) -> int | None:
        for index, cell in enumerate(header):
            if any(label in cell for label in labels):
                return index
        return None

    def _string_label(self, field: str, labels: tuple[str, ...]) -> str:
        value = self._label_value(labels)
        if value is None:
            raise ExtractionError(field, f"Missing label for {field}")
        return value

    def _date_label(self, field: str, labels: tuple[str, ...]) -> date:
        value = self._string_label(field, labels)
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ExtractionError(field, f"Expected ISO date, got {value!r}") from exc

    def _decimal_label(self, field: str, labels: tuple[str, ...]) -> Decimal:
        value = self._string_label(field, labels)
        return self._parse_decimal(value, field)

    def _int_label(self, field: str, labels: tuple[str, ...]) -> int:
        value = self._decimal_label(field, labels)
        return int(value)

    def _bool_label(self, field: str, labels: tuple[str, ...]) -> bool:
        value = self._string_label(field, labels).strip().lower()
        if value in {"yes", "true", "1", "y"}:
            return True
        if value in {"no", "false", "0", "n"}:
            return False
        raise ExtractionError(field, f"Expected yes/no value, got {value!r}")

    def _label_value(self, labels: tuple[str, ...]) -> str | None:
        for label in labels:
            pattern = rf"(?im)^\s*{re.escape(label)}\s*[:\-]\s*(.+?)\s*$"
            match = re.search(pattern, self._normalized)
            if match:
                return match.group(1).strip()
        return None

    def _ev_decimal(self, value: Decimal, raw_text: str) -> ExtractedValue[Decimal]:
        return ExtractedValue(
            value=value,
            source_document="uploaded_document.pdf",
            page_number=self._page_for(raw_text),
            extraction_method=ExtractionMethod.PDF_TABLE,
            confidence=ConfidenceLevel.MEDIUM,
            raw_text=raw_text,
        )

    def _ev_int(self, value: int, raw_text: str) -> ExtractedValue[int]:
        return ExtractedValue(
            value=value,
            source_document="uploaded_document.pdf",
            page_number=self._page_for(raw_text),
            extraction_method=ExtractionMethod.PDF_TABLE,
            confidence=ConfidenceLevel.MEDIUM,
            raw_text=raw_text,
        )

    def _ev_bool(self, value: bool, raw_text: str) -> ExtractedValue[bool]:
        return ExtractedValue(
            value=value,
            source_document="uploaded_document.pdf",
            page_number=self._page_for(raw_text),
            extraction_method=ExtractionMethod.PDF_TABLE,
            confidence=ConfidenceLevel.MEDIUM,
            raw_text=raw_text,
        )

    def _page_for(self, needle: str) -> int | None:
        page = 1
        for line in self._normalized.splitlines():
            match = re.match(r"=== Page (\d+) ===", line)
            if match:
                page = int(match.group(1))
            if needle.lower() in line.lower():
                return page
        return 1

    @staticmethod
    def _parse_decimal(value: str, field: str) -> Decimal:
        match = re.search(_NUMBER_PATTERN, value.replace(",", ""))
        if match is None:
            raise ExtractionError(field, f"No numeric value found in {value!r}")
        try:
            return Decimal(match.group(0))
        except InvalidOperation as exc:
            raise ExtractionError(field, f"Invalid decimal value {value!r}") from exc

    @staticmethod
    def _clean_cell(value: str) -> str:
        return " ".join(value.replace("\n", " ").split())
