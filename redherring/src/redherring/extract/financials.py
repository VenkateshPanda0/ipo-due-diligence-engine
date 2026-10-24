"""Financial-statement values from parsed tables, deterministically, with citations.

Row labels are matched by pattern, not by an LLM: issuers word the same line item in many ways
("Profit / (Loss) for the year (A)", "Restated profit for the period", "Profit after tax"), but the
set is small and closed, and a pattern miss leaves a gap instead of inventing a value.

Each value keeps the page of its own row, the row text, and the exact cell string; `verify` checks
those against the parsed document. Column meaning (period) comes from the parser's assembled
column headers; if a header carries no date the value is kept with `period=None` and lower
confidence rather than dropped or guessed.
"""

from __future__ import annotations

import re

from redherring.extract.models import CitedNumber, Concept
from redherring.extract.periods import parse_period
from redherring.parse.models import ParsedDocument, Table
from redherring.parse.units import parse_amount

_ROMAN = r"(?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx)"
# "- ", "(a) ", "iv. ", and a bare numeral as in "III Total Income" (Indian statements number lines)
_ENUMERATOR = re.compile(
    rf"^\s*(?:[-–•]\s*|\(?(?:[a-z]|[ivxlc]{{1,5}}|\d{{1,2}})[).]\s+|{_ROMAN}\s+(?=[a-z]))"
)
_NOTE_REF = re.compile(r"\((?:refer\s+)?notes?[^)]*\)")
_REJECT = re.compile(
    r"%|percent|per cent|growth|margin|\bratio\b|per share|\bdays\b|attributable|comprehensive|"
    r"\bas a\b|\bturnover\b|\bcagr\b|(?:including|incl\.?|after|net of) oci\b"
)
# qualifiers such as "(A)", "(net)" and a trailing formula like "(VIII) = (V-VII)"
_PARENS = r"(?:\s*\([^)]*\))*(?:\s*=\s*\([^)]*\))?"

# (concept, head pattern). The head must match the whole normalised label, optionally followed by
# parenthetical qualifiers such as "(A)", "(net)" or "(I= a+b)". First match wins.
_HEADS: tuple[tuple[Concept, str], ...] = (
    (Concept.REVENUE_FROM_OPERATIONS, r"(?:total )?revenue from operations"),
    (Concept.OTHER_INCOME, r"other income"),
    (Concept.TOTAL_INCOME, r"total income"),
    (Concept.TOTAL_EXPENSES, r"total expenses|total expenditure"),
    (
        Concept.PROFIT_BEFORE_TAX,
        r"(?:restated )?(?:net )?(?:profit|loss)(?:/\((?:loss|profit)\))? before tax"
        r"|(?:restated )?\(loss\)/profit before tax",
    ),
    (
        Concept.TAX_EXPENSE,
        r"total tax expenses?|tax expenses?|total income tax expenses?|income tax expenses?",
    ),
    (
        Concept.PROFIT_AFTER_TAX,
        r"(?:restated )?(?:net )?(?:profit|loss)(?:/\((?:loss|profit)\))?"
        r"(?: for the (?:year|period)(?:/(?:year|period))?| after tax)",
    ),
    (Concept.ADJUSTED_EBITDA, r"adjusted ebitda"),
    (Concept.EBITDA, r"ebitda"),
    (Concept.TOTAL_ASSETS, r"total assets"),
    (
        Concept.TOTAL_EQUITY_AND_LIABILITIES,
        r"total equity and liabilities|total liabilities and equity",
    ),
    (Concept.TOTAL_EQUITY, r"total equity"),
    (Concept.NET_WORTH, r"net worth"),
    (Concept.TOTAL_BORROWINGS, r"total borrowings"),
    (
        Concept.BORROWINGS,
        r"borrowings|(?:long|short)[- ]term borrowings|debt securities",
    ),
    (Concept.TRADE_RECEIVABLES, r"trade receivables"),
    (Concept.INVENTORIES, r"inventor(?:y|ies)"),
    (Concept.CASH_FROM_OPERATIONS, r"(?:net )?cash\b.*\boperating activit(?:y|ies)"),
    (Concept.CASH_FROM_INVESTING, r"(?:net )?cash\b.*\binvesting activit(?:y|ies)"),
    (Concept.CASH_FROM_FINANCING, r"(?:net )?cash\b.*\bfinancing activit(?:y|ies)"),
)
_COMPILED = tuple((c, re.compile(f"(?:{head}){_PARENS}")) for c, head in _HEADS)


def normalise_label(raw: str) -> str:
    """Lower-case a row label and strip enumerators, footnote marks and note references."""
    s = raw.lower().replace(" ", " ")
    s = re.sub(r"[#*†‡]+", "", s)
    while True:
        stripped = _ENUMERATOR.sub("", s, count=1)
        if stripped == s:
            break
        s = stripped
    s = _NOTE_REF.sub("", s)
    s = re.sub(r"\s*/\s*", "/", s)
    s = re.sub(r"\(\s+", "(", s)
    s = re.sub(r"\s+\)", ")", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(":").strip()
    return s


def concept_for_label(label: str) -> Concept | None:
    norm = normalise_label(label)
    if not norm or _REJECT.search(norm):
        return None
    for concept, pattern in _COMPILED:
        if pattern.fullmatch(norm):
            return concept
    return None


_REFERENCE_COLUMN = re.compile(r"^\s*(?:note|notes|anne\s*xure|sr\.?\s*no|s\.?\s*no)\b", re.I)
_ENUMERATOR_ONLY = re.compile(r"^\s*\(?(?:[a-z]|[ivxlc]{1,5}|\d{1,3})[).]?\s*$", re.I)


def _skip_column(header: str) -> bool:
    low = header.lower()
    if "%" in low or "percent" in low or "per cent" in low:
        return True
    return bool(_REFERENCE_COLUMN.match(header)) and parse_period(header) is None


def _label_index(rows: list[list[str]]) -> int:
    """Index of the column holding row labels.

    Usually 0, but SME statements put a serial ("(a)", "1") first, then the particulars. The label
    column is the first of the leading three whose cells are mostly words, not enumerators.
    """
    width = max((len(r) for r in rows), default=0)
    for j in range(min(width, 3)):
        cells = [r[j] for r in rows if j < len(r) and r[j].strip()]
        if not cells:
            continue
        words = sum(
            bool(re.search(r"[A-Za-z]{3,}", c)) and not _ENUMERATOR_ONLY.match(c) for c in cells
        )
        if words / len(cells) >= 0.5:
            return j
    return 0


def _looks_like_note_ref(cell: str, row: list[str]) -> bool:
    """A bare 1-2 digit integer next to decimal figures is a note number, not an amount."""
    if not re.fullmatch(r"\d{1,2}", cell.strip()):
        return False
    return any(re.search(r"[.,]", c) and parse_amount(c) is not None for c in row[1:])


def _confidence(has_period: bool, has_unit: bool, period_has_duration: bool) -> float:
    score = 0.5 + (0.25 if has_period else 0.0) + (0.15 if has_unit else 0.0)
    return min(1.0, score + (0.1 if period_has_duration else 0.0))


def _extract_table(table_id: int, t: Table) -> list[CitedNumber]:
    out: list[CitedNumber] = []
    body = t.rows[t.n_header_rows :]
    label_idx = _label_index(body)
    for i, row in enumerate(t.rows):
        if i < t.n_header_rows or label_idx >= len(row):
            continue
        label = row[label_idx]
        concept = concept_for_label(label)
        if concept is None:
            continue
        page = t.row_pages[i] if i < len(t.row_pages) else t.pdf_pages[0]
        span = " | ".join(c for c in row if c)
        for k in range(label_idx + 1, len(row)):
            cell = row[k]
            header = t.columns[k - 1] if 0 <= k - 1 < len(t.columns) else ""
            if _skip_column(header):
                continue
            value = parse_amount(cell)
            if value is None:
                continue
            period = parse_period(header)
            if period is None and _looks_like_note_ref(cell, row[label_idx:]):
                continue
            out.append(
                CitedNumber(
                    concept=concept,
                    label=label,
                    raw=cell,
                    value=value,
                    unit=t.unit,
                    period=period,
                    column_header=header,
                    pdf_page=page,
                    table_pages=t.pdf_pages,
                    table_id=table_id,
                    span=span,
                    confidence=_confidence(
                        period is not None,
                        t.unit is not None,
                        period is not None and (period.months is not None or period.instant),
                    ),
                )
            )
    return out


def extract_financials(doc: ParsedDocument) -> list[CitedNumber]:
    """Every statement-line value found in the document's tables, with evidence."""
    return [v for i, t in enumerate(doc.tables) for v in _extract_table(i, t)]
