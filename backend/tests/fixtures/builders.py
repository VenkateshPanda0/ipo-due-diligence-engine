"""Small builders for rule tests (on top of CompanyDataFactory)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.models.company_data import CompanyData, EligibilityDeclarations, FiscalYear
from app.models.enums import ConfidenceLevel, ExtractionMethod, FieldStatus
from app.models.extracted_value import ExtractedValue
from tests.fixtures.company_data_factory import CompanyDataFactory, clean_declarations


def ev(
    value: Any, *, low: bool = False, status: FieldStatus | None = None, confirmed: bool = False
) -> ExtractedValue[Any]:
    """ExtractedValue; ``low`` produces an unconfirmed OCR value (unreliable)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool) and isinstance(value, float):
        value = Decimal(str(value))
    return ExtractedValue(
        value=value,
        source_document="test.pdf",
        page_number=1,
        extraction_method=ExtractionMethod.OCR if (low or status) else ExtractionMethod.PDF_TABLE,
        confidence=ConfidenceLevel.LOW if low else ConfidenceLevel.HIGH,
        field_status=status,
        confirmed_by_human=confirmed,
    )


def D(x: str | int) -> Decimal:  # noqa: N802
    return Decimal(str(x))


def with_years(
    company: CompanyData,
    field: str,
    values: list[Any],
    *,
    labels: list[str] | None = None,
    months: list[int] | None = None,
) -> CompanyData:
    """Return a copy whose last len(values) fiscal years have ``field`` replaced.

    ``None`` in values removes the field; an ExtractedValue is used as-is.
    """
    fys = list(company.financials.fiscal_years)
    start = len(fys) - len(values)
    for i, v in enumerate(values):
        fy = fys[start + i]
        new_v = v if (v is None or isinstance(v, ExtractedValue)) else ev(D(v))
        upd: dict[str, Any] = {field: new_v}
        if months is not None:
            upd["months"] = months[i]
        fys[start + i] = fy.model_copy(update=upd)
    if labels is not None:
        fys = [
            fy.model_copy(update={"year_label": lbl}) for fy, lbl in zip(fys, labels, strict=True)
        ]
    return company.model_copy(
        update={"financials": company.financials.model_copy(update={"fiscal_years": fys})}
    )


def with_fiscal_years(company: CompanyData, fys: list[FiscalYear]) -> CompanyData:
    return company.model_copy(
        update={"financials": company.financials.model_copy(update={"fiscal_years": fys})}
    )


def update(company: CompanyData, section: str, **changes: Any) -> CompanyData:
    """Copy with ``section`` (e.g. 'issue_details') fields updated."""
    sub = getattr(company, section).model_copy(update=changes)
    return company.model_copy(update={section: sub})


def declarations(**changes: Any) -> EligibilityDeclarations:
    return clean_declarations().model_copy(update=changes)


def base() -> CompanyData:
    return CompanyDataFactory.create()
