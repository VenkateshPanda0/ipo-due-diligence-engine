"""Financial number parsing, unit detection, period parsing and label matching."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.intelligence.lexicon import match_label
from app.intelligence.numbers import detect_unit, parse_number, to_crore
from app.intelligence.periods import parse_period


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("12,34,56,789", Decimal("123456789")),
        ("123,456,789", Decimal("123456789")),
        ("1,00,000", Decimal("100000")),
        ("100,000", Decimal("100000")),
        ("(1,234.50)", Decimal("-1234.50")),
        ("1,234-", Decimal("-1234")),
        ("−45", Decimal("-45")),
        ("– 45", Decimal("-45")),
        ("₹ 1,23,456", Decimal("123456")),
        ("Rs. 99.5", Decimal("99.5")),
        ("15.00*", Decimal("15.00")),
        ("12,345.67(1)", Decimal("12345.67")),
        ("0", Decimal("0")),
        ("0.0001", Decimal("0.0001")),
    ],
)
def test_parse_number_values(token: str, expected: Decimal) -> None:
    assert parse_number(token).value == expected


@pytest.mark.parametrize("token", ["-", "—", "NA", "N/A", "n.a.", "Nil", "[●]", "•"])
def test_null_markers_are_not_zero(token: str) -> None:
    parsed = parse_number(token)
    assert parsed.value is None and parsed.is_null_marker


@pytest.mark.parametrize("token", ["1,2,3", "12,3456", "abc", "1.2.3", "(500)(2)", "", "12a"])
def test_malformed_numbers_abstain(token: str) -> None:
    assert parse_number(token).value is None


def test_percent_flag() -> None:
    p = parse_number("12.5%")
    assert p.is_percent and p.value == Decimal("12.5")


@settings(max_examples=300, deadline=None)
@given(
    st.integers(min_value=0, max_value=10**13),
    st.integers(min_value=0, max_value=99),
    st.booleans(),
)
def test_international_format_round_trip(n: int, frac: int, negative: bool) -> None:
    text = f"{n:,}.{frac:02d}"
    if negative:
        text = f"({text})"
    expected = Decimal(f"{n}.{frac:02d}") * (-1 if negative else 1)
    assert parse_number(text).value == expected


def _indian(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


@settings(max_examples=300, deadline=None)
@given(st.integers(min_value=0, max_value=10**13), st.sampled_from(["", "-", "trailing"]))
def test_indian_format_round_trip(n: int, sign: str) -> None:
    text = _indian(n)
    text = f"-{text}" if sign == "-" else (f"{text}-" if sign == "trailing" and n else text)
    expected = Decimal(n) * (-1 if sign and n else 1)
    assert parse_number(text).value == expected


@settings(max_examples=200, deadline=None)
@given(st.text(max_size=20))
def test_parse_number_never_raises(text: str) -> None:
    parse_number(text)


@pytest.mark.parametrize(
    ("unit", "value", "crore"),
    [
        ("INR_LAKH", "12345.67", "123.4567"),
        ("INR_MILLION", "1234.5", "123.45"),
        ("INR_CRORE", "7", "7"),
        ("INR_THOUSAND", "100000", "10"),
        ("INR", "10000000", "1"),
        ("INR_BILLION", "2", "200"),
    ],
)
def test_unit_conversion_exact(unit: str, value: str, crore: str) -> None:
    assert to_crore(Decimal(value), unit) == Decimal(crore)


@settings(max_examples=200, deadline=None)
@given(st.decimals(min_value=-(10**9), max_value=10**9, places=4, allow_nan=False))
def test_lakh_million_crore_consistency(v: Decimal) -> None:
    # 1 crore = 10 million = 100 lakh
    assert (
        to_crore(v * 100, "INR_LAKH") == to_crore(v * 10, "INR_MILLION") == to_crore(v, "INR_CRORE")
    )


def test_unknown_unit_rejected() -> None:
    with pytest.raises(ValueError):
        to_crore(Decimal(1), "USD")


@pytest.mark.parametrize(
    ("text", "unit"),
    [
        ("(₹ in lakhs)", "INR_LAKH"),
        ("(Rs. in million)", "INR_MILLION"),
        ("(Amount in ₹ crore, unless otherwise stated)", "INR_CRORE"),
        ("(in ₹ thousands)", "INR_THOUSAND"),
        ("(₹ in lakhs, except per share data)", "INR_LAKH"),
        ("(@ in takhs)", "INR_LAKH"),  # OCR misread
        ("(Min lakhs)", "INR_LAKH"),  # OCR merged '₹ in'
        ("in ₹ million and lakhs", None),  # ambiguous
        ("Particulars", None),
        ("Profit margin (%)", None),
        ("Revenue grew by 5 lakhs customers", None),  # no unit-declaration context
        ("net tangible assets of at least ₹ 30 million, calculated", None),  # an amount
        ("a net worth of not less than ₹ 1 crore (in ₹ lakhs)", "INR_LAKH"),
    ],
)
def test_detect_unit(text: str, unit: str | None) -> None:
    assert detect_unit(text) == unit


@pytest.mark.parametrize(
    ("text", "label", "months"),
    [
        ("March 31, 2024", "FY2024", 12),
        ("As at March 31, 2024", "FY2024", 12),
        ("31-Mar-24", "FY2024", 12),
        ("31.03.2023", "FY2023", 12),
        ("31st March, 2022", "FY2022", 12),
        ("Fiscal 2024", "FY2024", 12),
        ("FY 2023-24", "FY2024", 12),
        ("FY24", "FY2024", 12),
        ("2022-23", "FY2023", 12),
        ("Financial Year 2021-2022", "FY2022", 12),
        ("Six months ended September 30, 2024", "P2024-09-30-6M", 6),
        ("3 months ended 30 June 2024", "P2024-06-30-3M", 3),
        ("For the year ended December 31, 2023", "YE2023-12", 12),
    ],
)
def test_parse_period(text: str, label: str, months: int) -> None:
    p = parse_period(text)
    assert p is not None and p.label == label and p.months == months


@pytest.mark.parametrize(
    "text", ["Particulars", "Note 12", "2024", "2023-25", "Six months ended", ""]
)
def test_not_a_period(text: str) -> None:
    assert parse_period(text) is None


def test_period_end_dates() -> None:
    assert parse_period("FY 2023-24").end == date(2024, 3, 31)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("label", "field"),
    [
        ("Net tangible assets, as restated", "net_tangible_assets"),
        ("Monetary assets, as restated", "monetary_assets"),
        ("Operating profit, as restated", "operating_profit"),
        ("Net worth, as restated", "net_worth"),
        ("Revenue from operations", "revenue"),
        ("Restated profit for the year", "pat"),
        ("Total assets", "total_assets"),
        ("Equity share capital", "paid_up_capital"),
        ("Other equity", "reserves_and_surplus"),
        ("EBITDA", "ebitda"),
        ("Total equity", "net_worth"),
        # real-DRHP label variants (footnote digits, hyphens, units in labels)
        ("Net tangible assets1", "net_tangible_assets"),
        ("Net-worth (in ₹ million)", "net_worth"),
        ("Pre Tax Operating Profit", "operating_profit"),
        ("Pre-tax operating profit/ (loss)", "operating_profit"),
        ("Operating profit before tax", "operating_profit"),
    ],
)
def test_label_matches(label: str, field: str) -> None:
    m = match_label(label)
    assert m is not None and m.field == field


@pytest.mark.parametrize(
    "label",
    [
        "Restated Profit before tax",  # D9: PBT is not operating profit
        "EBIT",
        "Cash and cash equivalents",  # D9: not monetary assets by assumption
        "Monetary assets as a % of net tangible assets",
        "Return on Net Worth (%)",
        "Net Worth per share",
        "EBITDA Margin (%)",
        "Operating profit margin",
        "Total income",
        "Profit for the year attributable to non-controlling interest",
        "Net Asset Value per Equity Share",
        "Revenue growth (%)",
        "Average Operating Profit",  # an average is not a per-year value
        "Operating profit before working capital changes",  # cash-flow line
        "Tangible Net Worth (Rs. million)",  # industry / peer metric
        "profit after tax and OCI added in NCI",  # minority-interest adjustment
        "Profit for the year (as per the audited consolidated financial statements)",
        "Profit before tax",
    ],
)
def test_label_traps_do_not_match(label: str) -> None:
    m = match_label(label)
    assert m is None or m.field not in {
        "operating_profit",
        "monetary_assets",
        "net_worth",
        "revenue",
        "ebitda",
    }
