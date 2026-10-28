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
        ("T otal assets", "total assets"),  # a capital split from its word by kerning (Lenskart)
        ("T otal Current Liabilities", "total current liabilities"),
        ("R evenue from operations", "revenue from operations"),
        ("a loss on sale", "a loss on sale"),  # a real article is left alone
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
        ("T otal assets", Concept.TOTAL_ASSETS),
        ("Total tax expense / (credit) (VIII)", Concept.TAX_EXPENSE),
        ("Total tax expense/(credit)", Concept.TAX_EXPENSE),
        ("Net tax expenses", Concept.TAX_EXPENSE),
        ("Restated Profit/ (loss) for the period/ year (IX=", Concept.PROFIT_AFTER_TAX),  # wrapped
        (
            "Profit for the period / year from continuing operations (VIII-IX)",
            Concept.PROFIT_AFTER_TAX,
        ),
        ("Restated loss for", Concept.PROFIT_AFTER_TAX),  # label cut by a line wrap
        ("Profit for the period / year from continuing", Concept.PROFIT_AFTER_TAX),
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
        ("Restated Profit for the year, net of Tax", Concept.PROFIT_AFTER_TAX),
        ("Net Cash from Operating Activities (A) = i+ii+iii", Concept.CASH_FROM_OPERATIONS),
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


def test_right_aligned_numbers_under_left_aligned_headers_take_their_own_period() -> None:
    """Veritas: a ruled summary balance sheet whose figures sit one cell left of their 'As at'
    headers for three of the four columns; matching value columns to header columns in order."""
    pad = [""]
    at = ["As at", *pad * 2]
    header = ["Particulars", *pad * 3, *at, *at, *at, "As at", ""]
    dates = [
        *["", *pad * 3, "September 30, 2024", *pad * 2, "March 31, 2024", *pad * 2],
        *["March 31, 2023", *pad * 2, "March 31, 2022", ""],
    ]

    def figures(label: str, a: str, b: str, c: str, d: str) -> list[str]:
        return [label, *pad * 3, a, "", b, *pad * 2, c, *pad * 2, d, *pad * 2]

    rows = [
        header,
        dates,
        figures("Total Assets", "76,056.60", "64,215.93", "40,862.81", "26,424.74"),
        figures("Loans", "70,000.10", "50,000.20", "30,000.30", "20,000.40"),
    ]
    columns = [" ".join(x for x in (h, d) if x) for h, d in zip(header[1:], dates[1:], strict=True)]
    t = Table(
        pdf_pages=[78], row_pages=[78] * 4, unit=Unit.MILLION, columns=columns, rows=rows,
        n_header_rows=2,
    )  # fmt: skip
    got = {v.raw: v.period for v in extract_financials(_doc(t))}
    expected = {
        "76,056.60": date(2024, 9, 30),
        "64,215.93": date(2024, 3, 31),
        "40,862.81": date(2023, 3, 31),
        "26,424.74": date(2022, 3, 31),
    }
    for raw, end in expected.items():
        period = got[raw]
        assert period is not None and period.end == end, raw


def _stub_table(columns: list[str], rows: list[list[str]]) -> Table:
    return Table(
        pdf_pages=[7], row_pages=[7] * len(rows), unit=Unit.MILLION, columns=columns, rows=rows
    )


def test_bare_year_headers_take_the_wording_of_a_full_sibling_header() -> None:
    columns = ["", "2026", "Fiscal 2025", "2024"]
    rows = [["Restated profit for the year (I)", "(177.37)", "508.80", "727.57", "685.43"]]
    got = {v.raw: v.period for v in extract_financials(_doc(_stub_table(columns, rows)))}
    assert got["(177.37)"] is None
    for raw, year in (("508.80", 2026), ("727.57", 2025), ("685.43", 2024)):
        p = got[raw]
        assert p is not None and (p.end, p.months) == (date(year, 3, 31), 12), raw


def test_cash_generated_before_tax_is_not_operating_cash_flow_when_the_net_line_exists() -> None:
    columns = ["", "For the year ended March 31, 2026", "For the year ended March 31, 2025"]
    rows = [
        ["Cash generated from Operating Activities", "(480.16)", "(1,029.03)"],
        ["Net Cash from Operating Activities (A)", "(632.16)", "(1,361.19)"],
    ]
    values = extract_financials(_doc(_stub_table(columns, rows)))
    assert sorted(v.raw for v in values) == ["(1,361.19)", "(632.16)"]
    only_gross = extract_financials(_doc(_stub_table(columns, rows[:1])))
    assert len(only_gross) == 2  # with no net line the figure is all there is: still read


def test_a_bare_year_after_a_quarter_header_is_the_same_quarter_a_year_earlier() -> None:
    """Tata Capital: June-2025 quarter, '2024', 'Fiscal 2025', '2024', '2023' share one caption."""
    columns = [
        "As at June 30, / For the three months period ended June 30, 2025",
        "2024",
        "As at March 31, /Fiscal 2025",
        "2024",
        "2023",
    ]
    rows = [["Profit After Tax", "9,898.9", "4,616.6", "36,646.6", "31,502.1", "30,292.0"]]
    got = {v.raw: v.period for v in extract_financials(_doc(_stub_table(columns, rows)))}
    q, fy24 = got["4,616.6"], got["31,502.1"]
    assert q is not None and q.end == date(2024, 6, 30)
    assert fy24 is not None and fy24.end == date(2024, 3, 31)
    fy23 = got["30,292.0"]
    assert fy23 is not None and fy23.end == date(2023, 3, 31)


def test_a_leading_stub_column_left_of_years_that_hold_figures_stays_undated() -> None:
    """Tonbo: four figure columns (June-2026 stub, then three fiscal years) under three headers;
    the stub must not be read as a second FY2026 figure beside the real one."""
    columns = [
        "",
        "For the year ended March 31, 2026",
        "For the year ended March 31, 2025",
        "For the year ended March 31, 2024",
    ]
    rows = [
        ["Net Profit Before Tax", "(237.48)", "699.59", "992.65", "945.50"],
        ["Total income", "373.24", "3,699.39", "4,743.90", "4,318.96"],
    ]
    got = {v.raw: v.period for v in extract_financials(_doc(_stub_table(columns, rows)))}
    assert got["(237.48)"] is None
    for raw, year in (("699.59", 2026), ("992.65", 2025), ("945.50", 2024)):
        p = got[raw]
        assert p is not None and p.end == date(year, 3, 31), raw
