"""Unruled financial statements: rebuild rows and column headers from word geometry.

Restated financial statements in offer documents are typically unruled, right-aligned columns of
numbers. pdfplumber's text strategy needs stable left edges to find columns, which right-aligned
numbers lack, so it returns one fat column. Here a row is a text line whose trailing tokens are
values; value columns are the clusters of the values' right edges; header words (often split over
several lines, e.g. "For the year" / "ended March 31," / "2026") are assigned to the column they
sit over and joined top to bottom.
"""

from __future__ import annotations

import itertools
import re
import statistics
from dataclasses import dataclass
from typing import Any

from redherring.parse.models import BBox, RawTable
from redherring.parse.units import parse_amount

LINE_TOL = 3.0
MAX_NON_DATA_BETWEEN = 3  # more non-value lines than this between data rows starts a new table
MIN_DATA_ROWS = 3
MAX_HEADER_LINES = 8
ANCHOR_GAP = 10.0  # points: right edges closer than this are the same column

_NIL_TOKENS = {"-", "–", "—", "nil"}
_HEADERISH = re.compile(
    r"\b(as\s+(?:at|on)|year|period|ended|quarter|months?|for\s+the|particulars|notes?|fy|"
    r"restated|consolidated|standalone|unaudited|audited|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|\b(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
_YEAR = re.compile(r"^(?:19|20)\d{2}$")
_CAPTION = re.compile(r"amounts?\s+(?:are\s+)?in|all\s+amounts|₹\s*in|rs\.?\s*in", re.IGNORECASE)


def is_value(token: str) -> bool:
    return parse_amount(token) is not None or token.lower() in _NIL_TOKENS


def group_lines(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    lines: list[list[dict[str, Any]]] = []
    for w in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= LINE_TOL:
            lines[-1].append(w)
        else:
            lines.append([w])
    for line in lines:
        line.sort(key=lambda w: w["x0"])
    return lines


def line_bbox(line: list[dict[str, Any]]) -> BBox:
    return BBox(
        x0=min(w["x0"] for w in line),
        top=min(w["top"] for w in line),
        x1=max(w["x1"] for w in line),
        bottom=max(w["bottom"] for w in line),
    )


@dataclass
class _Line:
    words: list[dict[str, Any]]
    k: int  # number of trailing value tokens (0 = not a data row)

    @property
    def text(self) -> str:
        return " ".join(w["text"] for w in self.words)

    @property
    def label_words(self) -> list[dict[str, Any]]:
        return self.words[: len(self.words) - self.k]

    @property
    def value_words(self) -> list[dict[str, Any]]:
        return self.words[len(self.words) - self.k :] if self.k else []


def _classify(line: list[dict[str, Any]]) -> _Line:
    k = 0
    for w in reversed(line):
        if is_value(w["text"]):
            k += 1
        else:
            break
    if k < 2 or all(w["text"].lower() in _NIL_TOKENS for w in line[-k:]):
        k = 0
    elif all(_YEAR.match(w["text"]) for w in line[-k:]):
        k = 0  # "2026 2025": column-header years, not data
    return _Line(line, k)


def looks_numeric_tabular(words: list[dict[str, Any]]) -> bool:
    """Cheap gate: at least four lines with two or more numeric-looking tokens."""
    numeric = re.compile(r"^\(?[\d,]+(?:\.\d+)?\)?%?$")
    hits = sum(
        1 for line in group_lines(words) if sum(bool(numeric.match(w["text"])) for w in line) >= 2
    )
    return hits >= 4


def _anchors(xs: list[float]) -> list[float]:
    ordered = sorted(xs)
    clusters: list[list[float]] = [[ordered[0]]]
    for x in ordered[1:]:
        if x - clusters[-1][-1] <= ANCHOR_GAP:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [statistics.median(c) for c in clusters]


def _nearest(anchors: list[float], x: float) -> int:
    return min(range(len(anchors)), key=lambda j: abs(anchors[j] - x))


def _promote_aligned_rows(lines: list[_Line], first: int, last: int, anchors: list[float]) -> None:
    """Inside a statement, a line whose trailing value(s) sit on a column anchor is a data row
    even with a single value (e.g. an item that only has a prior-period figure)."""
    for ln in lines[first : last + 1]:
        if ln.k:
            continue
        run = 0
        for w in reversed(ln.words):
            if is_value(w["text"]):
                run += 1
            else:
                break
        tail = ln.words[len(ln.words) - run :] if run else []
        aligned = bool(tail) and all(
            abs(anchors[_nearest(anchors, w["x1"])] - w["x1"]) <= 1.5 * ANCHOR_GAP for w in tail
        )
        if aligned and not all(_YEAR.match(w["text"]) for w in tail):
            ln.k = run


def _place_values(
    ln: _Line, anchors: list[float], ncols: int, anchored: bool
) -> list[tuple[int, dict[str, Any]]] | None:
    """(column, word) for each value of `ln`, or None if they cannot sit one per column."""
    if not ln.k:
        return []
    if ln.k > ncols:
        return None
    if anchored:
        slots = [_nearest(anchors, w["x1"]) for w in ln.value_words]
        if len(set(slots)) != len(slots):  # collision: right-align positionally
            slots = list(range(ncols - ln.k, ncols))
    else:
        slots = list(range(ln.k))
    return list(zip(slots, ln.value_words, strict=True))


def _segments(lines: list[_Line]) -> list[tuple[int, int]]:
    """(first, last) line indices of each run of data rows, split on long non-data gaps."""
    data = [i for i, ln in enumerate(lines) if ln.k]
    if not data:
        return []
    heights = [ln.words[0]["bottom"] - ln.words[0]["top"] for ln in lines]
    typical = statistics.median(heights) or 8.0
    segs: list[list[int]] = [[data[0]]]
    for i in data[1:]:
        prev = segs[-1][-1]
        gap_lines = i - prev - 1
        gap_pts = lines[i].words[0]["top"] - lines[prev].words[0]["bottom"]
        if gap_lines > MAX_NON_DATA_BETWEEN or gap_pts > 6 * typical:
            segs.append([i])
        else:
            segs[-1].append(i)
    return [(s[0], s[-1]) for s in segs if len(s) >= MIN_DATA_ROWS]


def _header_start(lines: list[_Line], first: int, floor: int) -> int:
    """Index of the first header line above the data rows (== `first` if none)."""
    start = first
    while start > floor and first - start < MAX_HEADER_LINES:
        text = lines[start - 1].text
        if lines[start - 1].k or _CAPTION.search(text) or not _HEADERISH.search(text):
            break
        start -= 1
    return start


def _assign_header(header_lines: list[_Line], anchors: list[float]) -> tuple[str, list[str]]:
    n = len(anchors)
    if n == 1:
        bounds = [anchors[0] - 60.0, float("inf")]
    else:
        mids = [(a + b) / 2 for a, b in itertools.pairwise(anchors)]
        bounds = [anchors[0] - (anchors[1] - anchors[0]) / 2, *mids, float("inf")]
    label: list[str] = []
    cols: list[list[str]] = [[] for _ in range(n)]
    for ln in header_lines:
        for w in ln.words:
            cx = (w["x0"] + w["x1"]) / 2
            if cx < bounds[0]:
                label.append(w["text"])
                continue
            j = max(i for i in range(n) if bounds[i] <= cx)
            cols[j].append(w["text"])
    return " ".join(label), [" ".join(c) for c in cols]


def build_statement_tables(pdf_page: int, words: list[dict[str, Any]]) -> list[RawTable]:
    """Zero or more row-and-column tables from the numeric statement lines among `words`."""
    lines = [_classify(ln) for ln in group_lines(words)]
    tables: list[RawTable] = []
    floor = 0
    for first, last in _segments(lines):
        seg = lines[first : last + 1]
        value_x1 = [w["x1"] for ln in seg for w in ln.value_words]
        max_k = max(ln.k for ln in seg)
        anchors = _anchors(value_x1)
        anchored = len(anchors) <= max_k + 1
        if anchored:
            _promote_aligned_rows(lines, first, last, anchors)
        start = _header_start(lines, first, floor)
        header_lines = lines[start:first]
        ncols = len(anchors) if anchored else max_k

        rows: list[list[str]] = []
        for ln in seg:
            label = " ".join(w["text"] for w in ln.label_words)
            cells = [""] * ncols
            placed = _place_values(ln, anchors, ncols, anchored)
            if placed is None:  # cannot place one value per column: keep every token as text
                label = ln.text
            else:
                for slot, w in placed:
                    cells[slot] = w["text"]
            rows.append([label, *cells])

        label_header, columns = ("", [""] * ncols)
        if anchored and header_lines:
            label_header, columns = _assign_header(header_lines, anchors)
        elif header_lines:  # positional mode: keep header lines as label-only text
            label_header = " ".join(ln.text for ln in header_lines)

        boxes = [line_bbox(ln.words) for ln in lines[start : last + 1]]
        tables.append(
            RawTable(
                pdf_page=pdf_page,
                bbox=BBox(
                    x0=min(b.x0 for b in boxes),
                    top=min(b.top for b in boxes),
                    x1=max(b.x1 for b in boxes),
                    bottom=max(b.bottom for b in boxes),
                ),
                rows=rows,
                strategy="numeric_rows",
                columns=columns if anchored else [],
                label_header=label_header,
            )
        )
        floor = last + 1
    return tables
