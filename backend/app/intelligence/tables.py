"""
Stage D — financial table reconstruction.

Two independent strategies produce ``FinancialTable`` objects:

* geometric — works on native and OCR words: finds a header line containing at
  least two reporting periods, then assigns each numeric token below it to the
  nearest period column by x-position. Wrapped row labels are merged, and tables
  that continue onto the next page without a header inherit the previous header.
* vector — pdfplumber's ruled-table extraction, interpreted by column index.

Units and statement basis (consolidated / standalone) are taken from captions
near the table. Nothing is normalised here; values keep their source text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.intelligence.layout import Cell, Line, Word
from app.intelligence.numbers import ParsedNumber, detect_unit, parse_number
from app.intelligence.pages import PageData
from app.intelligence.periods import Period, parse_period

_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
_NOTE_SUFFIX_RE = re.compile(r"\s+(?:\d{1,2}(?:\.\d{1,2})?|[ivx]{1,4}|\([a-z0-9]{1,3}\))$", re.I)
_LEADING_ENUM_RE = re.compile(r"^(?:\(?[a-z0-9ivx]{1,4}[).]\s+)", re.I)
_MAX_BLANK_LINES = 6
_ELIGIBILITY_RE = re.compile(r"eligib|regulation\s*6\s*\(|reg\.\s*6\s*\(", re.I)


@dataclass
class PeriodColumn:
    period: Period
    x0: float
    x1: float
    header_text: str
    basis: str | None = None  # per-column basis when the header annotates it

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class CellValue:
    parsed: ParsedNumber
    text: str
    conf: float | None = None


@dataclass
class TableRow:
    label: str
    raw_label: str
    values: dict[str, CellValue]
    line_text: str
    page: int
    top: float


@dataclass
class FinancialTable:
    table_id: str
    page: int
    method: str  # "geometric" | "vector"
    columns: list[PeriodColumn]
    rows: list[TableRow] = field(default_factory=list)
    unit: str | None = None
    unit_source: str | None = None
    basis: str | None = None  # "consolidated" | "standalone" | None
    title: str = ""
    continued_from: str | None = None
    eligibility_context: bool = False  # header sits under an ICDR eligibility discussion
    ocr: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def period_labels(self) -> list[str]:
        return [c.period.label for c in self.columns]


def _cell_periods(cell: Cell) -> list[PeriodColumn]:
    """Split a cell into one or more period columns (handles merged header cells)."""
    words = cell.words
    out: list[PeriodColumn] = []
    i = 0
    while i < len(words):
        found = None
        for j in range(i + 1, min(i + 7, len(words)) + 1):
            period = parse_period(" ".join(w.text for w in words[i:j]))
            if period is not None:
                found = (j, period)
                break
        if found is None:
            i += 1
            continue
        j, period = found
        # tighten the start: "Particulars March 31, 2025" must start at "March"
        while i + 1 < j:
            tighter = parse_period(" ".join(w.text for w in words[i + 1 : j]))
            if tighter is None or tighter.label != period.label:
                break
            i, period = i + 1, tighter
        out.append(
            PeriodColumn(period, words[i].x0, words[j - 1].x1, " ".join(w.text for w in words[i:j]))
        )
        i = j
    return out


def _valid(cols: list[PeriodColumn]) -> bool:
    labels = [c.period.label for c in cols]
    return (
        len(cols) >= 2
        and len(set(labels)) == len(labels)
        and not any(b.x0 < a.x1 - 1 for a, b in zip(cols, cols[1:], strict=False))
    )


def find_period_columns(line: Line, previous: Line | list[Line] | None) -> list[PeriodColumn]:
    """Return ≥2 distinct, left-to-right period columns for a header line, else [].

    ``previous`` is the line (or up to two lines) immediately above, used for
    multi-line headers such as "Fiscal" / "Description" above a row of bare years.
    """
    above_lines = [previous] if isinstance(previous, Line) else list(previous or [])
    cols: list[PeriodColumn] = []
    for cell in line.cells:
        cols.extend(_cell_periods(cell))
    # Header words split across cells ("March" | "31," | "2025"): also search the whole
    # line and keep whichever reading finds more columns.
    whole = _cell_periods(Cell(list(line.words)))
    if _valid(whole) and (not _valid(cols) or len(whole) > len(cols)):
        cols = whole
    if len(cols) < 2 and above_lines:
        # Multi-line header: "Fiscal" / "As at March 31," above a row of bare years.
        years = [w for w in line.words if _YEAR_RE.match(w.text)]
        above = " ".join(a.text for a in above_lines).lower()
        if (
            len(years) >= 2
            and len(years) >= len(line.words) - 2
            and re.search(r"fiscal|\bfy\b|march\s*31|year", above)
        ):
            cols = [
                PeriodColumn(
                    Period(f"FY{int(w.text)}", None, 12),
                    w.x0,
                    w.x1,
                    f"{above_lines[-1].text} {w.text}",
                )
                for w in years
            ]
    labels = [c.period.label for c in cols]
    if len(cols) < 2 or len(set(labels)) != len(labels):
        return []
    if any(b.x0 < a.x1 - 1 for a, b in zip(cols, cols[1:], strict=False)):
        return []
    return cols


def _clean_label(text: str) -> str:
    label = _LEADING_ENUM_RE.sub("", text.strip())
    prev = None
    while prev != label:
        prev = label
        label = _NOTE_SUFFIX_RE.sub("", label).strip()
    return " ".join(label.split())


def _context(
    lines: list[Line],
    header_index: int,
    page: PageData,
    prev_tail: list[Line] | None = None,
) -> tuple[str | None, str | None, str | None, str]:
    """Return (unit, unit_source, basis, title) from lines above the header.

    When the header sits near the top of the page, the last lines of the previous
    page are searched too (captions are often printed before a page break).
    """
    unit = detect_unit(lines[header_index].text)
    source = "header" if unit else None
    basis: str | None = None
    title_lines: list[str] = []
    above = list(lines[:header_index])
    if prev_tail and header_index < 6:
        above = list(prev_tail[-8:]) + above
    h = len(above)
    for k in range(h - 1, max(-1, h - 15), -1):
        text = above[k].text
        low = text.lower()
        if unit is None and k >= h - 10:
            unit = detect_unit(text)
            source = "caption" if unit else None
        if basis is None:
            has_c, has_s = "consolidated" in low, "standalone" in low
            if has_c != has_s:
                basis = "consolidated" if has_c else "standalone"
        if len(title_lines) < 3 and text.strip():
            title_lines.insert(0, text.strip())
    if unit is None:
        for line in page.lines[:12]:
            unit = detect_unit(line.text)
            if unit:
                source = "page_heading"
                break
    if basis is None:
        top = " ".join(line.text.lower() for line in page.lines[:12])
        has_c, has_s = "consolidated" in top, "standalone" in top
        if has_c != has_s:
            basis = "consolidated" if has_c else "standalone"
    return unit, source, basis, " / ".join(title_lines)[:300]


_BASIS_RE = re.compile(r"\(?\b(consolidated|standalone)\b\)?", re.I)


def _column_basis(lines: list[Line], header_index: int, columns: list[PeriodColumn]) -> int:
    """Read per-column "(Consolidated)" / "(Standalone)" annotations next to the header.

    Sets ``PeriodColumn.basis`` in place and returns how many lines directly below
    the header were consumed as annotation lines (they must not be parsed as rows).
    """
    consumed = 0
    for offset in (1, 2, -1):
        k = header_index + offset
        if k < 0 or k >= len(lines):
            continue
        line = lines[k]
        words = [w for w in line.words if _BASIS_RE.fullmatch(w.text.strip())]
        # an annotation line consists (almost) only of basis words
        if not words or len(words) < len(line.words) - 1:
            if offset > 0:
                break
            continue
        for w in words:
            col = _assign(w, columns)
            if col is not None and col.basis is None:
                col.basis = _BASIS_RE.fullmatch(w.text.strip()).group(1).lower()  # type: ignore[union-attr]
        if offset > 0:
            consumed = offset
    return consumed


def _eligibility_context(
    lines: list[Line], header_index: int, prev_tail: list[Line] | None
) -> bool:
    """True when the ~40 lines above the header discuss ICDR eligibility (Reg 6)."""
    above = [ln.text for ln in lines[max(0, header_index - 40) : header_index]]
    if header_index < 40 and prev_tail:
        above = [ln.text for ln in prev_tail[-(40 - header_index) :]] + above
    return any(_ELIGIBILITY_RE.search(t) for t in above)


def _assign(word: Word, columns: list[PeriodColumn]) -> PeriodColumn | None:
    spacing = min((b.xc - a.xc for a, b in zip(columns, columns[1:], strict=False)), default=80.0)
    best, dist = None, 1e9
    for col in columns:
        d = min(abs(word.xc - col.xc), abs(word.x1 - col.x1))
        if d < dist:
            best, dist = col, d
    return best if dist <= max(spacing * 0.6, 12.0) else None


def _numeric_word(word: Word) -> ParsedNumber | None:
    parsed = parse_number(word.text)
    if parsed.value is not None or parsed.is_null_marker:
        return parsed
    return None


def _merge_numeric_words(words: list[Word]) -> list[Word]:
    """Re-join tokens split by the PDF, e.g. '(1,234.5' + ')' or '₹' + '1,234'."""
    out: list[Word] = []
    for w in words:
        if (
            out
            and (w.text in (")", "%") or out[-1].text in ("(", "₹", "Rs.", "Rs", "-"))
            and w.x0 - out[-1].x1 < 4
        ):
            prev = out.pop()
            conf = min((c for c in (prev.conf, w.conf) if c is not None), default=None)
            joiner = "" if w.text in (")", "%") or prev.text in ("(", "-") else " "
            out.append(
                Word(
                    prev.text + joiner + w.text,
                    prev.x0,
                    w.x1,
                    min(prev.top, w.top),
                    max(prev.bottom, w.bottom),
                    conf,
                )
            )
        else:
            out.append(w)
    return out


def _parse_row(line: Line, columns: list[PeriodColumn]) -> tuple[str, dict[str, CellValue] | None]:
    """Split a line into (label, values by period label).

    Returns ``(label, None)`` when the numbers cannot be placed unambiguously —
    a number outside every column, two numbers competing for one column, or more
    numbers than columns. Guessing here would silently shift values between years.
    """
    left_edge = (
        columns[0].x0 - max((columns[1].x0 - columns[0].x1) * 0.6, 10.0)
        if len(columns) > 1
        else columns[0].x0 - 20
    )
    label_words: list[Word] = []
    values: dict[str, CellValue] = {}
    ambiguous = False
    numbers = 0
    prose_words = 0
    for w in _merge_numeric_words(line.words):
        parsed = _numeric_word(w) if w.xc >= left_edge else None
        if parsed is None:
            if w.xc < left_edge:
                label_words.append(w)
            elif any(ch.isalpha() for ch in w.text):
                prose_words += 1
            continue
        numbers += 1
        col = _assign(w, columns)
        if col is None or col.period.label in values:
            ambiguous = True
            continue
        values[col.period.label] = CellValue(parsed, w.text, w.conf)
    label = " ".join(w.text for w in label_words)
    if prose_words >= 3:
        # running text across the value columns (notes, narrative): not a table row
        return label, {}
    if ambiguous or numbers > len(columns):
        return label, None
    return label, values


def geometric_tables(
    page: PageData, carry: FinancialTable | None, prev_tail: list[Line] | None = None
) -> list[FinancialTable]:
    """Reconstruct period tables on one page.

    ``carry`` is the last table of the previous page; ``prev_tail`` its last lines
    (searched for unit / basis captions printed just before the page break).
    """
    tables: list[FinancialTable] = []
    lines = page.lines
    current: FinancialTable | None = None
    blank_run = 0
    pending_label = ""
    # Continuation: rows at the top of the page before any header inherit the previous header.
    if carry is not None and lines:
        current = FinancialTable(
            f"p{page.number}-t0",
            page.number,
            "geometric",
            carry.columns,
            unit=carry.unit,
            unit_source=carry.unit_source,
            basis=carry.basis,
            title=carry.title,
            continued_from=carry.table_id,
            eligibility_context=carry.eligibility_context,
            ocr=page.method == "ocr",
        )
    skip_until = -1
    for idx, line in enumerate(lines):
        if idx <= skip_until:
            continue
        cols = find_period_columns(line, lines[max(0, idx - 2) : idx])
        if cols:
            if current is not None and current.rows:
                tables.append(current)
            unit, source, basis, title = _context(lines, idx, page, prev_tail)
            skip_until = idx + _column_basis(lines, idx, cols)
            current = FinancialTable(
                f"p{page.number}-t{len(tables) + 1}",
                page.number,
                "geometric",
                cols,
                unit=unit,
                unit_source=source,
                basis=basis,
                title=title,
                eligibility_context=_eligibility_context(lines, idx, prev_tail),
                ocr=page.method == "ocr",
            )
            # A repeated header on a continuation page restarts with the same columns.
            if (
                carry is not None
                and [c.period.label for c in cols] == carry.period_labels
                and idx < 8
            ):
                current.continued_from = carry.table_id
                current.unit = current.unit or carry.unit
                current.basis = current.basis or carry.basis
                current.eligibility_context |= carry.eligibility_context
            blank_run, pending_label = 0, ""
            continue
        if current is None:
            continue
        label, parsed_values = _parse_row(line, current.columns)
        if parsed_values is None:
            current.warnings.append(f"row skipped (column mismatch): {label[:60]}")
            blank_run, pending_label = 0, ""
            continue
        values = parsed_values
        if not values:
            blank_run += 1
            if label:
                pending_label = f"{pending_label} {label}".strip() if pending_label else label
            if blank_run > _MAX_BLANK_LINES:
                if current.rows:
                    tables.append(current)
                current, pending_label = None, ""
            continue
        blank_run = 0
        raw = label
        if pending_label and (not label or label[:1].islower() or len(label) < 3):
            raw = f"{pending_label} {label}".strip()
        pending_label = ""
        current.rows.append(
            TableRow(_clean_label(raw), raw, values, line.text, page.number, line.top)
        )
    if current is not None and current.rows:
        tables.append(current)
    return tables


def vector_tables(page: PageData) -> list[FinancialTable]:
    """Interpret pdfplumber ruled tables that carry a period header row."""
    out: list[FinancialTable] = []
    for t_index, grid in enumerate(page.native_tables):
        rows = [[(c or "").replace("\n", " ").strip() for c in row] for row in grid if row]
        header_idx: int | None = None
        col_periods: dict[int, Period] = {}
        for r_index, row in enumerate(rows[:4]):
            parsed_cells = {i: parse_period(cell) for i, cell in enumerate(row) if cell}
            found = {i: p for i, p in parsed_cells.items() if p is not None}
            if len(found) >= 2 and len({p.label for p in found.values()}) == len(found):
                header_idx, col_periods = r_index, found
                break
        if header_idx is None:
            continue
        columns = [
            PeriodColumn(p, float(i), float(i) + 1, rows[header_idx][i])
            for i, p in sorted(col_periods.items())
        ]
        header_text = " ".join(" ".join(r) for r in rows[: header_idx + 1])
        unit = detect_unit(header_text)
        table = FinancialTable(
            f"p{page.number}-v{t_index + 1}",
            page.number,
            "vector",
            columns,
            unit=unit,
            unit_source="header" if unit else None,
        )
        if table.unit is None or table.basis is None:
            # borrow caption context from the geometric view of the same page
            for line_idx, line in enumerate(page.lines):
                if find_period_columns(line, page.lines[max(0, line_idx - 2) : line_idx]):
                    u, s, b, title = _context(page.lines, line_idx, page)
                    table.unit = table.unit or u
                    table.unit_source = table.unit_source or s
                    table.basis, table.title = b, title
                    table.eligibility_context = _eligibility_context(page.lines, line_idx, None)
                    break
        for row in rows[header_idx + 1 :]:
            label_cells = [
                c
                for i, c in enumerate(row)
                if i not in col_periods and c and parse_number(c).value is None
            ]
            values = {}
            for i, period in col_periods.items():
                if i < len(row) and row[i]:
                    parsed = parse_number(row[i])
                    if parsed.value is not None or parsed.is_null_marker:
                        values[period.label] = CellValue(parsed, row[i])
            if values and label_cells:
                raw = " ".join(label_cells)
                table.rows.append(
                    TableRow(_clean_label(raw), raw, values, " | ".join(row), page.number, 0.0)
                )
        if table.rows:
            out.append(table)
    return out


def extract_tables(pages: list[PageData]) -> list[FinancialTable]:
    """Run both strategies over all pages, carrying table context across page breaks."""
    tables: list[FinancialTable] = []
    carry: FinancialTable | None = None
    prev_tail: list[Line] | None = None
    for page in pages:
        if not page.lines:
            carry, prev_tail = None, None
            continue
        page_tables = geometric_tables(page, carry, prev_tail)
        prev_tail = page.lines[-40:]
        tables.extend(page_tables)
        # carry a table forward only if it ran to the bottom of the page
        carry = None
        if page_tables:
            last = page_tables[-1]
            if last.rows and last.rows[-1].top > page.height * 0.7:
                carry = last
        tables.extend(vector_tables(page))
    return tables
