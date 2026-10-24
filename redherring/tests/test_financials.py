from datetime import date
from decimal import Decimal

import pytest

from redherring.extract.financials import (
    concept_for_label,
    extract_financials,
    normalise_label,
)
from redherring.extract.models import Concept
from redherring.parse.models import ParsedDocument, ParsedPage, Table
from redherring.parse.units import Unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("I. Revenue from operations", "revenue from operations"),
        ("a) Revenue from operations (net)", "revenue from operations (net)"),
        ("(i) Total income#", "total income"),
        ("- Fees and commission income", "fees and commission income"),
        ("Profit / (Loss) for the year (A)", "profit/(loss) for the year (a)"),
        (
            "Net cash flow from operating activities (refer note 40):",
            "net cash flow from operating activities",
        ),
        ("  Total   assets  ", "total assets"),
        ("III Total Income (I+II)", "total income (i+ii)"),  # roman numeral without a full stop
        ("VII Profit/(Loss) Before Tax (V-VI)", "profit/(loss) before tax (v-vi)"),
        ("Civil works", "civil works"),  # "civil" is not a numeral
        ("Mix of products", "mix of products"),
    ],
)
def test_normalise_label(raw: str, expected: str) -> None:
    assert normalise_label(raw) == expected


@pytest.mark.parametrize(
    ("label", "concept"),
    [
        ("Revenue from operations", Concept.REVENUE_FROM_OPERATIONS),
        ("I. Revenue from operations (net)", Concept.REVENUE_FROM_OPERATIONS),
        ("Total revenue from operations", Concept.REVENUE_FROM_OPERATIONS),
        ("Other income", Concept.OTHER_INCOME),
        ("Total income (I= a+b)", Concept.TOTAL_INCOME),
        ("Total Income", Concept.TOTAL_INCOME),
        ("Total expenses", Concept.TOTAL_EXPENSES),
        ("Profit before tax", Concept.PROFIT_BEFORE_TAX),
        ("Restated profit/(loss) before tax", Concept.PROFIT_BEFORE_TAX),
        ("Total tax expense", Concept.TAX_EXPENSE),
        ("Profit for the year", Concept.PROFIT_AFTER_TAX),
        ("Restated profit for the period (A)", Concept.PROFIT_AFTER_TAX),
        ("Profit/(loss) after tax", Concept.PROFIT_AFTER_TAX),
        ("Profit / (Loss) for the year", Concept.PROFIT_AFTER_TAX),
        ("Restated profit for the period/year (VIII) = (V-VII)", Concept.PROFIT_AFTER_TAX),
        ("Restated profit for the year/period", Concept.PROFIT_AFTER_TAX),
        ("I Total Revenue from Operations", Concept.REVENUE_FROM_OPERATIONS),
        ("VII Profit/(Loss) Before Tax (V-VI)", Concept.PROFIT_BEFORE_TAX),
        ("IX Profit/(loss) for the year (VII-VIII)", Concept.PROFIT_AFTER_TAX),
        ("Net Cash from/(used in) Operating Activity (A)", Concept.CASH_FROM_OPERATIONS),
        (
            "Total Revenue",
            Concept.TOTAL_INCOME,
        ),  # SME wording; "Total revenue from operations" is not
        ("III. Total Revenue (I + II)", Concept.TOTAL_INCOME),
        ("Profit/Loss before Taxation", Concept.PROFIT_BEFORE_TAX),
        ("Profit before taxation", Concept.PROFIT_BEFORE_TAX),
        ("Net Profit /Loss after adjustments", Concept.PROFIT_AFTER_TAX),
        ("Profit/Loss After Tax but Before Extra ordinary Items", Concept.PROFIT_AFTER_TAX),
        ("EBITDA", Concept.EBITDA),
        ("EBITDA(3) (in ₹ million)", Concept.EBITDA),
        ("Adjusted EBITDA (G = E+F)", Concept.ADJUSTED_EBITDA),
        ("Total borrowings", Concept.TOTAL_BORROWINGS),
        ("(i) Borrowings", Concept.BORROWINGS),
        ("Long Term Borrowings", Concept.BORROWINGS),
        ("Total assets", Concept.TOTAL_ASSETS),
        ("Total equity", Concept.TOTAL_EQUITY),
        ("Total equity and liabilities", Concept.TOTAL_EQUITY_AND_LIABILITIES),
        ("Net worth", Concept.NET_WORTH),
        ("Trade receivables", Concept.TRADE_RECEIVABLES),
        ("Inventories", Concept.INVENTORIES),
        ("Net cash generated from operating activities", Concept.CASH_FROM_OPERATIONS),
        ("Net cash flow from/(used in) investing activities", Concept.CASH_FROM_INVESTING),
        ("Net cash (used in) financing activities", Concept.CASH_FROM_FINANCING),
    ],
)
def test_concept_for_label(label: str, concept: Concept) -> None:
    assert concept_for_label(label) is concept


@pytest.mark.parametrize(
    "label",
    [
        "Revenue from operations as a % of total income",
        "EBITDA margin (%)",
        "Total income growth",
        "Profit before tax margin",
        "Particulars",
        "Income",
        "Other comprehensive income for the year",
        "Restated profit for the period/year before exceptional items (net of tax) (IX)",
        "Profit attributable to owners of the company",
        "3. Net Profit after tax (Including OCI)",  # total comprehensive income, not profit
        "PAT after OCI",
        "",
    ],
)
def test_concept_for_label_rejects(label: str) -> None:
    assert concept_for_label(label) is None


def _doc(*tables: Table) -> ParsedDocument:
    page = ParsedPage(
        pdf_page=1, width=612, height=792, alnum_chars=100, n_images=0, image_coverage=0.0,
        needs_ocr=False,
    )  # fmt: skip
    return ParsedDocument(doc_id="t", n_pages=9, pages=[page], tables=list(tables))


def _pnl(**kw: object) -> Table:
    base: dict[str, object] = {
        "pdf_pages": [5, 6],
        "rows": [
            ["Revenue from operations", "31", "1,000.50", "900.25"],
            ["Other income", "32", "12.75", "(9.10)"],
            ["Total income", "", "1,013.25", "891.15"],
            ["Revenue from operations as a % of total income", "", "98.74", "101.02"],
            ["Particulars", "", "", ""],
        ],
        "row_pages": [5, 5, 6, 6, 6],
        "columns": [
            "Note",
            "For the year ended March 31, 2026",
            "For the year ended March 31, 2025",
        ],
        "unit": Unit.LAKH,
        "unit_text": "Rs. in Lakhs",
    }
    base.update(kw)
    return Table.model_validate(base)


def test_extracts_values_with_period_unit_page_and_span() -> None:
    values = extract_financials(_doc(_pnl()))
    rev = [v for v in values if v.concept is Concept.REVENUE_FROM_OPERATIONS]
    assert [(v.period.end if v.period else None, v.value) for v in rev] == [
        (date(2026, 3, 31), Decimal("1000.50")),
        (date(2025, 3, 31), Decimal("900.25")),
    ]
    v = rev[0]
    assert v.unit is Unit.LAKH
    assert v.raw == "1,000.50"
    assert v.pdf_page == 5
    assert "Revenue from operations" in v.span
    assert "1,000.50" in v.span
    assert v.rupees == Decimal("100050000.00")


def test_page_comes_from_the_row_not_the_table_start() -> None:
    values = extract_financials(_doc(_pnl()))
    total = next(v for v in values if v.concept is Concept.TOTAL_INCOME)
    assert total.pdf_page == 6  # row 3 sits on the second page of the stitched table


def test_bracketed_values_are_negative_and_note_column_is_ignored() -> None:
    values = extract_financials(_doc(_pnl()))
    other = [v for v in values if v.concept is Concept.OTHER_INCOME]
    assert [v.value for v in other] == [Decimal("12.75"), Decimal("-9.10")]
    assert not any(v.column_header == "Note" for v in values)


def test_percentage_and_ratio_rows_are_not_extracted() -> None:
    values = extract_financials(_doc(_pnl()))
    assert all("%" not in v.label for v in values)


def test_percentage_columns_are_skipped() -> None:
    t = Table.model_validate(
        {
            "pdf_pages": [1],
            "rows": [["Total income", "18,507.93", "100.00", "10,507.14", "100.00"]],
            "row_pages": [1],
            "columns": [
                "Fiscal 2026 Amount (Rs. in million)",
                "Fiscal 2026 Percentage of total income (%)",
                "Fiscal 2025 Amount (Rs. in million)",
                "Fiscal 2025 Percentage of total income (%)",
            ],
            "unit": Unit.MILLION,
        }
    )
    values = extract_financials(_doc(t))
    assert [v.value for v in values] == [Decimal("18507.93"), Decimal("10507.14")]


def test_header_rows_of_a_ruled_table_are_not_data() -> None:
    t = Table.model_validate(
        {
            "pdf_pages": [1],
            "rows": [
                ["Particulars", "Fiscal 2026", "Fiscal 2025"],
                ["Total income", "100", "90"],
            ],
            "row_pages": [1, 1],
            "columns": ["Fiscal 2026", "Fiscal 2025"],
            "n_header_rows": 1,
            "unit": Unit.CRORE,
        }
    )
    values = extract_financials(_doc(t))
    assert [(v.concept, v.value) for v in values] == [
        (Concept.TOTAL_INCOME, Decimal(100)),
        (Concept.TOTAL_INCOME, Decimal(90)),
    ]


def test_unknown_period_and_unit_lower_confidence_but_are_kept() -> None:
    t = Table.model_validate(
        {
            "pdf_pages": [1],
            "rows": [["Total income", "100", "90"]],
            "row_pages": [1],
            "columns": ["", ""],
        }
    )
    (a, _b) = extract_financials(_doc(t))
    assert a.period is None
    assert a.unit is None
    assert a.rupees is None
    known = extract_financials(_doc(_pnl()))[0]
    assert a.confidence < known.confidence


def test_dash_and_blank_cells_produce_no_value() -> None:
    t = Table.model_validate(
        {
            "pdf_pages": [1],
            "rows": [["Inventories", "-", "", "12.5"]],
            "row_pages": [1],
            "columns": ["FY 2026", "FY 2025", "FY 2024"],
            "unit": Unit.CRORE,
        }
    )
    values = extract_financials(_doc(t))
    assert [(v.value, v.period.end.year if v.period else None) for v in values] == [
        (Decimal("12.5"), 2024)
    ]


def test_label_column_is_detected_when_serial_numbers_come_first() -> None:
    """SME layout: serial | particulars | annexure no. | values (the Synoptics statements)."""
    t = Table.model_validate(
        {
            "pdf_pages": [44, 45],
            "rows": [
                ["PARTICULARS", "", "Anne xure Nos.", "AS AT 30- Sept-22", "AS AT 31-Mar-22"],
                ["1", "Income", "", "", ""],
                ["(a)", "Revenue From Operations", "22", "2,375.73", "5,092.32"],
                ["(b)", "Other Income", "23", "1.66", "4.75"],
                ["2", "Total Income (1a+1b)", "", "2,377.39", "5,097.07"],
            ],
            "row_pages": [44, 44, 44, 44, 45],
            "columns": ["", "Anne xure Nos.", "AS AT 30- Sept-22", "AS AT 31-Mar-22"],
            "n_header_rows": 1,
            "unit": Unit.LAKH,
        }
    )
    values = extract_financials(_doc(t))
    assert [(v.concept, v.raw, v.period.end.isoformat() if v.period else None) for v in values] == [
        (Concept.REVENUE_FROM_OPERATIONS, "2,375.73", "2022-09-30"),
        (Concept.REVENUE_FROM_OPERATIONS, "5,092.32", "2022-03-31"),
        (Concept.OTHER_INCOME, "1.66", "2022-09-30"),
        (Concept.OTHER_INCOME, "4.75", "2022-03-31"),
        (Concept.TOTAL_INCOME, "2,377.39", "2022-09-30"),
        (Concept.TOTAL_INCOME, "5,097.07", "2022-03-31"),
    ]
    assert all("Revenue" in v.span or "Income" in v.span for v in values)
    # annexure numbers (22, 23) are never read as amounts
    assert not any(v.raw in {"22", "23"} for v in values)


def test_annexure_and_serial_columns_are_skipped_by_header() -> None:
    t = Table.model_validate(
        {
            "pdf_pages": [1],
            "rows": [["Total income", "7", "100.00"]],
            "row_pages": [1],
            "columns": ["Annexure", "FY 2026"],
            "unit": Unit.CRORE,
        }
    )
    assert [v.raw for v in extract_financials(_doc(t))] == ["100.00"]
