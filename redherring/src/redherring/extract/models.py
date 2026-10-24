"""Extraction output model. Every extracted number carries its evidence.

A value is never reported without the PDF page it came from, the text span (the table row) that
contains it, the exact string as printed, and how it was obtained. `verify` re-checks these.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from redherring.extract.periods import Period
from redherring.parse.units import MULTIPLIER, Unit


class Concept(StrEnum):
    REVENUE_FROM_OPERATIONS = "revenue_from_operations"
    OTHER_INCOME = "other_income"
    TOTAL_INCOME = "total_income"
    TOTAL_EXPENSES = "total_expenses"
    PROFIT_BEFORE_TAX = "profit_before_tax"
    TAX_EXPENSE = "tax_expense"
    PROFIT_AFTER_TAX = "profit_after_tax"
    EBITDA = "ebitda"
    ADJUSTED_EBITDA = "adjusted_ebitda"
    TOTAL_ASSETS = "total_assets"
    TOTAL_EQUITY = "total_equity"
    NET_WORTH = "net_worth"
    TOTAL_EQUITY_AND_LIABILITIES = "total_equity_and_liabilities"
    TOTAL_BORROWINGS = "total_borrowings"
    BORROWINGS = "borrowings"  # a component line (non-current, current, debt securities ...)
    TRADE_RECEIVABLES = "trade_receivables"
    INVENTORIES = "inventories"
    CASH_FROM_OPERATIONS = "cash_from_operations"
    CASH_FROM_INVESTING = "cash_from_investing"
    CASH_FROM_FINANCING = "cash_from_financing"


# Balance-sheet items: measured at a date, not over a period.
STOCK_CONCEPTS = frozenset(
    {
        Concept.TOTAL_ASSETS,
        Concept.TOTAL_EQUITY,
        Concept.TOTAL_EQUITY_AND_LIABILITIES,
        Concept.NET_WORTH,
        Concept.TOTAL_BORROWINGS,
        Concept.BORROWINGS,
        Concept.TRADE_RECEIVABLES,
        Concept.INVENTORIES,
    }
)


class CitedNumber(BaseModel):
    """One number read from a table cell, with its evidence."""

    concept: Concept
    label: str = Field(description="Row label exactly as printed")
    raw: str = Field(description="Cell text exactly as printed, e.g. '(1,234.50)'")
    value: Decimal = Field(
        description="Parsed value in the table's own unit (negative if bracketed)"
    )
    unit: Unit | None = Field(description="Table unit; None means unknown, never 'rupees'")
    period: Period | None
    column_header: str = Field(description="Header text of the column the value sits in")
    pdf_page: int = Field(description="Physical PDF page of the row")
    table_pages: list[int]
    table_id: int = Field(description="Index of the source table in ParsedDocument.tables")
    span: str = Field(description="The table row, cells joined by ' | ', that contains `raw`")
    method: str = "table_row"
    confidence: float = Field(ge=0.0, le=1.0)

    @property
    def rupees(self) -> Decimal | None:
        """Value in rupees, or None when the unit is unknown."""
        return None if self.unit is None else self.value * MULTIPLIER[self.unit]
