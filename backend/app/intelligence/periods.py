"""
Reporting-period detection from column headers and captions.

Recognised forms (case-insensitive), e.g.:
  "March 31, 2024", "31 March 2024", "31-Mar-24", "31.03.2024", "As at March 31, 2024"
  "Fiscal 2024", "Fiscal Year 2024", "FY 2024", "FY24", "FY 2023-24", "2023-24"
  "Six months ended September 30, 2024" (stub: months=6)

Labels: Indian financial years ending 31 March are labelled ``FY<end year>``
(``FY2024`` = 1 Apr 2023 – 31 Mar 2024). Other year-ends are labelled
``YE<yyyy-mm>``; stub periods ``P<yyyy-mm-dd>-<n>M``. A period is never inferred
from a bare four-digit number in the middle of free text.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
_MONTHS["sept"] = 9
_MONTH_RE = "|".join(sorted((re.escape(m) for m in _MONTHS), key=len, reverse=True))
_NUM_WORDS = {"three": 3, "six": 6, "nine": 9, "twelve": 12, "3": 3, "6": 6, "9": 9, "12": 12}

_DATE_PATTERNS = (
    re.compile(rf"\b(?P<mon>{_MONTH_RE})\.?\s+(?P<day>\d{{1,2}}),?\s+(?P<year>\d{{4}})", re.I),
    re.compile(
        rf"(?<!\d)(?P<day>\d{{1,2}})(?:st|nd|rd|th)?[\s\-]+(?P<mon>{_MONTH_RE})\.?,?[\s\-]+(?P<year>\d{{2,4}})",
        re.I,
    ),
    re.compile(r"(?<!\d)(?P<day>\d{1,2})[./-](?P<mnum>\d{1,2})[./-](?P<year>\d{4})"),
)
_FY_RANGE_RE = re.compile(
    r"(?:fy|fiscal|financial\s+year)?\s*'?(?P<y1>\d{4})\s*[-–/]\s*(?P<y2>\d{2,4})\b", re.I
)
_FY_SINGLE_RE = re.compile(
    r"\b(?:fy|fiscal(?:\s+year)?|financial\s+year)\s*'?(?P<y>\d{4}|\d{2})\b", re.I
)
_STUB_RE = re.compile(r"(?P<n>three|six|nine|3|6|9)\s*(?:-|\s)?months?\s+(?:period\s+)?ended", re.I)


@dataclass(frozen=True)
class Period:
    """A reporting period."""

    label: str
    end: date | None
    months: int

    @property
    def is_full_year(self) -> bool:
        return self.months == 12


def _year(y: str) -> int:
    v = int(y)
    return v + 2000 if v < 100 else v


def _make(end: date, months: int) -> Period:
    if months != 12:
        return Period(f"P{end.isoformat()}-{months}M", end, months)
    if end.month == 3:
        return Period(f"FY{end.year}", end, 12)
    return Period(f"YE{end.year}-{end.month:02d}", end, 12)


def _parse_date(text: str) -> date | None:
    for pat in _DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        gd = m.groupdict()
        try:
            month = int(gd["mnum"]) if gd.get("mnum") else _MONTHS[gd["mon"].lower().rstrip(".")]
            return date(_year(gd["year"]), month, int(gd["day"]))
        except (KeyError, ValueError):
            continue
    return None


def parse_period(text: str) -> Period | None:
    """Parse a header cell / caption into a Period, or None if not a period."""
    if not text or len(text) > 160:
        return None
    t = " ".join(text.split())
    stub = _STUB_RE.search(t)
    months = _NUM_WORDS[stub.group("n").lower()] if stub else 12
    end = _parse_date(t)
    if end is not None:
        return _make(end, months)
    if stub:
        return None  # stub without a parseable end date: do not guess
    m = _FY_RANGE_RE.search(t)
    if m:
        y1, y2 = int(m.group("y1")), _year(m.group("y2"))
        if y2 == y1 + 1:
            return Period(f"FY{y2}", date(y2, 3, 31), 12)
        return None
    m = _FY_SINGLE_RE.search(t)
    if m:
        y = _year(m.group("y"))
        if 1990 <= y <= 2100:
            return Period(f"FY{y}", date(y, 3, 31), 12)
    return None
