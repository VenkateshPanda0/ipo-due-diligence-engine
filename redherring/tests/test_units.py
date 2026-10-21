from decimal import Decimal

import pytest

from redherring.parse.units import Unit, detect_unit, parse_amount, to_rupees


@pytest.mark.parametrize(
    ("text", "unit"),
    [
        ("(₹ in lakhs)", Unit.LAKH),
        ("(Rs. in Million)", Unit.MILLION),
        ("All amounts in ₹ crore, unless otherwise stated", Unit.CRORE),
        ("(Amount in INR Lacs)", Unit.LAKH),
        ("₹ Million", Unit.MILLION),
        ("(in Rs. '000)", Unit.THOUSAND),
        ("Rs. in crores", Unit.CRORE),
    ],
)
def test_detect_unit(text: str, unit: Unit) -> None:
    hit = detect_unit(text)
    assert hit is not None
    assert hit[0] is unit


@pytest.mark.parametrize(
    "text",
    [
        "Revenue from operations",
        "increase in crease of shareholding",  # 'in' + 'cr...' must not match
        "number of shares held in 2000",
        "",
    ],
)
def test_detect_unit_no_false_positive(text: str) -> None:
    assert detect_unit(text) is None


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("1,23,456.78", Decimal("123456.78")),
        ("12,345", Decimal(12345)),
        ("(1,234.5)", Decimal("-1234.5")),
        ("-45", Decimal(-45)),
        ("−45", Decimal(-45)),  # Unicode minus
        ("₹ 12.5", Decimal("12.5")),
        ("Rs. 1,000", Decimal(1000)),
        ("Nil", Decimal(0)),
        ("1,234*", Decimal(1234)),
        ("0.75", Decimal("0.75")),
    ],
)
def test_parse_amount(cell: str, expected: Decimal) -> None:
    assert parse_amount(cell) == expected


@pytest.mark.parametrize("cell", ["", "-", "–", "NA", "N.A.", "Revenue", "12 34", "1,2,3", "12%"])
def test_parse_amount_none(cell: str) -> None:
    assert parse_amount(cell) is None


def test_parse_amount_percent_opt_in() -> None:
    assert parse_amount("12.5%", allow_percent=True) == Decimal("12.5")


def test_to_rupees() -> None:
    assert to_rupees(Decimal("1.5"), Unit.CRORE) == Decimal(15_000_000)
    assert to_rupees(Decimal(250), Unit.LAKH) == Decimal(25_000_000)
    assert to_rupees(Decimal(2), Unit.MILLION) == Decimal(2_000_000)
    # 1 crore == 10 million == 100 lakh
    assert to_rupees(Decimal(1), Unit.CRORE) == to_rupees(Decimal(10), Unit.MILLION)
    assert to_rupees(Decimal(1), Unit.CRORE) == to_rupees(Decimal(100), Unit.LAKH)
