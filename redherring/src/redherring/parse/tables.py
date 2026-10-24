"""Table post-processing: cell cleaning, multi-page stitching, orientation detection.

Heuristics here are deliberately conservative and are measured on real documents in the M0
parse report. Anything uncertain is left as found and flagged rather than silently "fixed".
"""

from __future__ import annotations

import re

from redherring.extract.periods import parse_period
from redherring.parse.models import RawTable, Table
from redherring.parse.units import parse_amount

_PERIOD = re.compile(
    r"""(?ix)
    (?:\b(?:fy|f\.y\.|fiscal(?:\s+year)?|year\s+ended|as\s+at|as\s+on)\s*)?
    (?:
        (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+(?:19|20)\d{2}
      | \b(?:19|20)\d{2}\s*[-–/]\s*(?:\d{2}|(?:19|20)\d{2})\b
      | \b(?:fy|f\.y\.)\s*'?(?:19|20)?\d{2}\b
      | \b(?:19|20)\d{2}\b
    )
    """
)


_YEAR_ONLY = re.compile(r"^(?:19|20)\d{2}$")
MAX_HEADER_ROWS = 8


def _is_money_cell(cell: str) -> bool:
    return parse_amount(cell) is not None and not _YEAR_ONLY.match(cell.strip())


def header_info(rows: list[list[str]]) -> tuple[list[str], str, int]:
    """(value-column headers, label-column header, number of header rows) of a ruled table.

    Header rows are the leading rows with no money-like value in any value column, provided data
    rows follow. Cells of each column are joined top to bottom, so a header split over rows
    ("Fiscal 2026" / "Amount" / "(Rs. in million)") becomes one string per column.
    """
    n = 0
    while n < min(len(rows), MAX_HEADER_ROWS) and not any(_is_money_cell(c) for c in rows[n][1:]):
        n += 1
    if n == 0 or n == len(rows):
        return [], "", 0
    width = max(len(r) for r in rows[:n])
    padded = [r + [""] * (width - len(r)) for r in rows[:n]]
    columns = [" ".join(c for c in (r[j] for r in padded) if c) for j in range(1, width)]
    label = " ".join(c for c in (r[0] for r in padded) if c)
    return columns, label, n


def clean_cell(cell: object) -> str:
    return re.sub(r"\s+", " ", str(cell or "")).strip()


def clean_rows(rows: list[list[object]]) -> list[list[str]]:
    cleaned = [[clean_cell(c) for c in row] for row in rows]
    return [r for r in cleaned if any(r)]


def is_period_label(cell: str) -> bool:
    return bool(cell) and bool(_PERIOD.search(cell))


def looks_transposed(rows: list[list[str]]) -> bool:
    """True if periods run down the first column instead of across the header row.

    Indian offer documents mostly show line items as rows and periods as columns; some issuers
    (and some PDF extractions) flip this. We call a table transposed when most body cells in the
    first column are period labels and most header cells (beyond the first) are not.
    """
    if len(rows) < 3 or len(rows[0]) < 3:
        return False
    first_col = [r[0] for r in rows[1:] if r and r[0]]
    header = [c for c in rows[0][1:] if c]
    if not first_col or not header:
        return False
    col_hits = sum(is_period_label(c) for c in first_col) / len(first_col)
    hdr_hits = sum(is_period_label(c) for c in header) / len(header)
    return col_hits >= 0.6 and hdr_hits <= 0.3


def transpose(rows: list[list[str]]) -> list[list[str]]:
    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    return [list(col) for col in zip(*padded, strict=True)]


ANCHOR_TOLERANCE = 4.0  # points: same column layout if every right edge is this close
MAX_INHERIT_PAGES = 2  # look back at most this many pages for a header


def _same_layout(a: list[float], b: list[float]) -> bool:
    return len(a) == len(b) > 0 and all(
        abs(x - y) <= ANCHOR_TOLERANCE for x, y in zip(a, b, strict=True)
    )


def inherit_headers(raw: list[RawTable]) -> None:
    """Give headerless statement tables the header of the nearest table above with the same layout.

    A statement continuing onto the next page (or below a page-break of its own) has no header
    lines; the table above it with identical column positions is the one it continues. The source
    page is recorded in `header_inherited_from` so the inference is never silent.
    """
    ordered = sorted(
        (t for t in raw if t.strategy == "numeric_rows"), key=lambda t: (t.pdf_page, t.bbox.top)
    )
    for i, t in enumerate(ordered):
        if t.anchors and not any(t.columns):
            for prev in reversed(ordered[:i]):
                if t.pdf_page - prev.pdf_page > MAX_INHERIT_PAGES:
                    break
                if any(prev.columns) and _same_layout(prev.anchors, t.anchors):
                    t.columns = list(prev.columns)
                    t.label_header = t.label_header or prev.label_header
                    t.unit = t.unit or prev.unit
                    t.unit_text = t.unit_text or prev.unit_text
                    t.header_inherited_from = prev.pdf_page
                    break


MAX_UNIT_PAGES = 2  # a caption counts for statements at most this many pages after it


def _period_signature(columns: list[str]) -> tuple[str, ...]:
    """The fiscal period each column header names, e.g. ('2022-03-31', '2021-03-31')."""
    sig = [p.end.isoformat() for c in columns if (p := parse_period(c))]  # "Note No." has none
    return tuple(sig) if len(sig) >= 2 else ()


def inherit_units(raw: list[RawTable]) -> None:
    """Give a statement without a unit caption the unit of the sibling statements before it.

    Some filings print "(Amount Rs. In Lakh)" over the balance sheet and income statement but not
    over the cash-flow statement two pages on. The unit is borrowed only from tables within two
    pages whose columns name exactly the same dates, only if all such tables agree, and never from
    a table that itself borrowed. The source page is recorded in `unit_inherited_from`.
    """
    ordered = sorted(raw, key=lambda t: (t.pdf_page, t.bbox.top))
    for i, t in enumerate(ordered):
        if t.unit is not None or not t.columns:
            continue
        sig = _period_signature(t.columns)
        if not sig:
            continue
        donors = [
            d
            for d in ordered[:i]
            if d.unit is not None
            and d.unit_inherited_from is None
            and 0 <= t.pdf_page - d.pdf_page <= MAX_UNIT_PAGES
            and _period_signature(d.columns) == sig
        ]
        if donors and len({d.unit for d in donors}) == 1:
            src = donors[-1]
            t.unit = src.unit
            t.unit_text = f"inherited from page {src.pdf_page}: {src.unit_text}"
            t.unit_inherited_from = src.pdf_page


def _continues(prev: RawTable, nxt: RawTable, page_heights: dict[int, float]) -> bool:
    """Does `nxt` (top of page p+1) look like the continuation of `prev` (bottom of page p)?"""
    if nxt.pdf_page != prev.pdf_page + 1:
        return False
    h_prev = page_heights[prev.pdf_page]
    h_next = page_heights[nxt.pdf_page]
    if prev.bbox.bottom < 0.80 * h_prev or nxt.bbox.top > 0.25 * h_next:
        return False
    widths = {len(r) for r in prev.rows}, {len(r) for r in nxt.rows}
    prev_w = max(widths[0])
    next_w = max(widths[1])
    if prev_w != next_w:
        return False
    # A table with a header of its own that differs from the one above is a new statement (a
    # balance sheet followed by an income statement), not a tail of it.
    if nxt.n_header_rows and any(nxt.columns) and any(prev.columns) and nxt.columns != prev.columns:
        return False
    # If the next table carries a different unit declaration it is a new table, not a tail.
    return not (nxt.unit and prev.unit and nxt.unit != prev.unit)


def stitch_tables(raw: list[RawTable], page_heights: dict[int, float]) -> list[Table]:
    """Merge tables that run across consecutive pages; flag (never flip) suspect orientation."""
    ordered = sorted(raw, key=lambda t: (t.pdf_page, t.bbox.top))
    groups: list[list[RawTable]] = []
    for t in ordered:
        if groups and _continues(groups[-1][-1], t, page_heights):
            groups[-1].append(t)
        else:
            groups.append([t])

    tables: list[Table] = []
    for g in groups:
        rows = [list(r) for r in g[0].rows]
        row_pages = [g[0].pdf_page] * len(rows)
        header = rows[0] if rows else []
        for cont in g[1:]:
            tail = [list(r) for r in cont.rows]
            if tail and header and tail[0] == header:  # repeated header row
                tail = tail[1:]
            rows.extend(tail)
            row_pages.extend([cont.pdf_page] * len(tail))
        unit = next((t.unit for t in g if t.unit), None)
        unit_text = next((t.unit_text for t in g if t.unit), None)
        tables.append(
            Table(
                pdf_pages=sorted({t.pdf_page for t in g}),
                rows=rows,
                row_pages=row_pages,
                unit=unit,
                unit_text=unit_text,
                columns=next((t.columns for t in g if t.columns), []),
                label_header=next((t.label_header for t in g if t.label_header), ""),
                n_header_rows=g[0].n_header_rows,
                header_inherited_from=next(
                    (t.header_inherited_from for t in g if t.header_inherited_from), None
                ),
                unit_inherited_from=next(
                    (t.unit_inherited_from for t in g if t.unit_inherited_from), None
                ),
                transposed_suspect=looks_transposed(rows),
                stitched_from=len(g),
            )
        )
    return tables
