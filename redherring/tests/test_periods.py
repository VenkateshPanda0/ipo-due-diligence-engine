from datetime import date

import pytest

from redherring.extract.periods import Period, parse_period, period_key


@pytest.mark.parametrize(
    ("header", "end", "months", "instant"),
    [
        ("For the year ended March 31, 2026", date(2026, 3, 31), 12, False),
        ("For the year ended 31 March 2025", date(2025, 3, 31), 12, False),
        ("Year ended 31-Mar-2024", date(2024, 3, 31), 12, False),
        ("For the year ended 31-03-2023", date(2023, 3, 31), 12, False),
        ("For the year ended 31.03.2022", date(2022, 3, 31), 12, False),
        ("Fiscal 2026", date(2026, 3, 31), 12, False),
        ("FY 2025", date(2025, 3, 31), 12, False),
        ("FY2021", date(2021, 3, 31), 12, False),
        ("Fiscal Year 2024-25", date(2025, 3, 31), 12, False),
        ("FY 2023-24", date(2024, 3, 31), 12, False),
        ("For the three month period ended June 30, 2026", date(2026, 6, 30), 3, False),
        ("For the six months ended September 30, 2025", date(2025, 9, 30), 6, False),
        ("For the nine month period ended December 31, 2025", date(2025, 12, 31), 9, False),
        ("As at March 31, 2026", date(2026, 3, 31), None, True),
        ("As on 31st March 2025", date(2025, 3, 31), None, True),
        ("As at and for FY 2021", date(2021, 3, 31), 12, False),
        ("31-Mar-22", date(2022, 3, 31), None, False),
        ("AS AT 31-Mar-22", date(2022, 3, 31), None, True),
        ("AS AT 30- Sept-22", date(2022, 9, 30), None, True),
        ("As on Sept. 30, 2022", date(2022, 9, 30), None, True),
        ("30-Jun-2025", date(2025, 6, 30), None, False),
        ("For the year ended 31-Mar-99", date(1999, 3, 31), 12, False),
    ],
)
def test_parse_period(header: str, end: date, months: int | None, instant: bool) -> None:
    p = parse_period(header)
    assert p is not None, header
    assert (p.end, p.months, p.instant) == (end, months, instant)


@pytest.mark.parametrize("header", ["", "Particulars", "Note", "Amount", "(Rs. in million)", "%"])
def test_parse_period_none(header: str) -> None:
    assert parse_period(header) is None


def test_date_only_header_has_unknown_duration() -> None:
    p = parse_period("March 31, 2026")
    assert p == Period(end=date(2026, 3, 31), months=None, instant=False)


def test_first_date_wins_when_header_lists_several() -> None:
    p = parse_period("For the year ended March 31, 2026 and 2025")
    assert p is not None
    assert p.end == date(2026, 3, 31)


@pytest.mark.parametrize(
    ("header", "key"),
    [
        ("For the year ended March 31, 2026", "FY2026"),
        ("Fiscal 2025", "FY2025"),
        ("For the three month period ended June 30, 2026", "3M-2026-06-30"),
        ("As at March 31, 2026", "AT-2026-03-31"),
        ("March 31, 2026", "?-2026-03-31"),
        ("For the year ended December 31, 2024", "12M-2024-12-31"),  # non-March year end
    ],
)
def test_period_key(header: str, key: str) -> None:
    p = parse_period(header)
    assert p is not None
    assert period_key(p) == key
