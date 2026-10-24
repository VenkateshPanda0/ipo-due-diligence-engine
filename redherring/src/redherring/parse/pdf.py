"""PDF -> page-tagged blocks and tables.

pypdfium2 (fast) answers "does this page have a text layer / images?"; pdfplumber supplies word
geometry and table finding. Both are permissively licensed. No OCR happens here: pages with no
text layer but images are flagged `needs_ocr` so scanned content is reported, not silently lost.
"""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pdfplumber
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from redherring.parse.models import (
    PARSER_VERSION,
    BBox,
    Block,
    ParsedDocument,
    ParsedPage,
    RawTable,
)
from redherring.parse.statements import build_statement_tables, looks_numeric_tabular
from redherring.parse.statements import group_lines as _group_lines
from redherring.parse.statements import line_bbox as _line_bbox
from redherring.parse.tables import (
    clean_rows,
    header_info,
    inherit_headers,
    inherit_units,
    stitch_tables,
)
from redherring.parse.units import detect_unit, parse_amount

MIN_ALNUM_FOR_TEXT_LAYER = 25
LINE_TOL = 3.0  # points: words whose `top` differ by less are on the same line
UNIT_LOOKBACK = 90.0  # points above a table searched for a unit caption
_PAGE_NO = re.compile(r"^\s*(?:page\s+)?(\d{1,4}|[ivxlcdm]{1,8})\s*$", re.IGNORECASE)


def _page_image_stats(pdfium_page: Any) -> tuple[int, float]:
    """(number of image objects, fraction of page area they cover)."""
    width, height = pdfium_page.get_size()
    area = max(width * height, 1.0)
    n = 0
    covered = 0.0
    for obj in pdfium_page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,)):
        n += 1
        left, bottom, right, top = obj.get_bounds()
        covered += max(right - left, 0.0) * max(top - bottom, 0.0)
    return n, min(covered / area, 1.0)


def _inside(w: dict[str, Any], boxes: Iterable[BBox]) -> bool:
    cx, cy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
    return any(b.x0 <= cx <= b.x1 and b.top <= cy <= b.bottom for b in boxes)


def _blocks_from_words(
    pdf_page: int, words: list[dict[str, Any]], table_boxes: list[BBox]
) -> list[Block]:
    body = [w for w in words if not _inside(w, table_boxes)]
    blocks: list[Block] = []
    cur: list[list[dict[str, Any]]] = []
    prev_bottom: float | None = None
    prev_height = 0.0

    def flush() -> None:
        if not cur:
            return
        text = "\n".join(" ".join(w["text"] for w in ln) for ln in cur)
        boxes = [_line_bbox(ln) for ln in cur]
        blocks.append(
            Block(
                pdf_page=pdf_page,
                text=text,
                bbox=BBox(
                    x0=min(b.x0 for b in boxes),
                    top=min(b.top for b in boxes),
                    x1=max(b.x1 for b in boxes),
                    bottom=max(b.bottom for b in boxes),
                ),
            )
        )

    for ln in _group_lines(body):
        box = _line_bbox(ln)
        height = box.bottom - box.top
        if prev_bottom is not None and box.top - prev_bottom > 0.9 * max(height, prev_height):
            flush()
            cur = []
        cur.append(ln)
        prev_bottom, prev_height = box.bottom, height
    flush()
    return blocks


def _printed_page(words: list[dict[str, Any]], height: float) -> str | None:
    """Printed page number from the bottom (then top) margin, if it looks like one."""
    lines = _group_lines(words)
    if not lines:
        return None
    for line in (lines[-1], lines[0]):  # footer first, then header
        box = _line_bbox(line)
        if box.top > 0.90 * height or box.bottom < 0.08 * height:
            text = " ".join(w["text"] for w in line)
            if m := _PAGE_NO.match(text):
                return m.group(1)
    return None


def _without_overlapping_spaces(page: Any) -> Any:
    """Return `page`, minus whitespace chars that sit on top of a glyph.

    Some generators right-align numbers with padding spaces positioned inside the first digit's
    box. Sorted by x, such a space lands between the digit and the rest of the number and splits
    "9,521.29" into "9" and ",521.29". Real inter-word spaces lie between glyphs, never inside one.
    """
    chars = page.chars
    glyphs: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for c in chars:
        if not c["text"].isspace():
            glyphs[round(c["top"])].append((c["x0"], c["x1"]))
    drop: set[tuple[float, float]] = set()
    for c in chars:
        if not c["text"].isspace():
            continue
        mid = (c["x0"] + c["x1"]) / 2
        key = round(c["top"])
        if any(
            x0 + 0.3 < mid < x1 - 0.3
            for k in (key - 1, key, key + 1)
            for x0, x1 in glyphs.get(k, ())
        ):
            drop.add((c["x0"], c["top"]))
    if not drop:
        return page
    return page.filter(
        lambda o: (
            not (
                o.get("object_type") == "char"
                and o["text"].isspace()
                and (o["x0"], o["top"]) in drop
            )
        )
    )


_WHITE = ((1,), (1.0,), (1, 1, 1), (1.0, 1.0, 1.0), (0, 0, 0, 0), (0.0, 0.0, 0.0, 0.0))
MIN_VISIBLE_SIZE = 1.0  # points: below this no reader can read a character
OFF_PAGE_MARGIN = 5.0


def _is_white(color: Any) -> bool:
    if isinstance(color, (int, float)):
        color = (color,)
    return isinstance(color, (tuple, list)) and tuple(color) in _WHITE


def _hidden_text(page: Any) -> tuple[Any, int, int]:
    """(page without unreadable characters, number removed, number of invisible white characters).

    A filing's text layer is what the extractor reads, but a reader sees only what is drawn. Text
    far smaller than a point or entirely outside the page cannot be seen and is dropped (a
    document could otherwise carry "our Company has appointed X as the monitoring agency" where
    nobody will look). White text is common on coloured headers, so it is kept, and counted only
    when nothing coloured sits behind it: the page is then reported as carrying invisible text.
    """
    width, height = float(page.width), float(page.height)
    boxes = [
        (r["x0"], r["top"], r["x1"], r["bottom"])
        for r in [*page.rects, *page.curves]  # charts and arrows are curves, not rectangles
        if r.get("fill") and not _is_white(r.get("non_stroking_color"))
    ]
    boxes += [(i["x0"], i["top"], i["x1"], i["bottom"]) for i in page.images]
    removed: set[tuple[float, float]] = set()
    invisible = 0
    for c in page.chars:
        if c["text"].isspace():
            continue
        off = (
            c["x1"] < -OFF_PAGE_MARGIN
            or c["x0"] > width + OFF_PAGE_MARGIN
            or c["bottom"] < -OFF_PAGE_MARGIN
            or c["top"] > height + OFF_PAGE_MARGIN
        )
        if c["size"] < MIN_VISIBLE_SIZE or off:
            removed.add((c["x0"], c["top"]))
        elif _is_white(c.get("non_stroking_color")):
            cx, cy = (c["x0"] + c["x1"]) / 2, (c["top"] + c["bottom"]) / 2
            if not any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in boxes):
                invisible += 1
    if not removed:
        return page, 0, invisible
    kept = page.filter(
        lambda o: not (o.get("object_type") == "char" and (o["x0"], o["top"]) in removed)
    )
    return kept, len(removed), invisible


def _overlaps_vertically(a: BBox, b: BBox) -> bool:
    inter = min(a.bottom, b.bottom) - max(a.top, b.top)
    return inter > 0.5 * min(a.bottom - a.top, b.bottom - b.top)


_PLAIN_YEAR = re.compile(r"^(?:19|20)\d{2}$")


def _money_tokens(cell: str) -> int:
    """Count money-like tokens in a cell. A bare year ("2026") is a label, not an amount."""
    return sum(
        parse_amount(t) is not None
        and ("," in t or "." in t or len(t) >= 3)
        and not _PLAIN_YEAR.match(t)
        for t in cell.split()
    )


def _has_merged_cells(rows: list[list[str]]) -> bool:
    """Several values fused into one cell: a ruled box whose row rules are missing."""
    per_cell = [_money_tokens(c) for r in rows for c in r]
    return any(n >= 3 for n in per_cell) or sum(n >= 2 for n in per_cell) >= 2


def _numeric_density(rows: list[list[str]]) -> float:
    cells = [c for r in rows for c in r if c]
    return sum(parse_amount(c) is not None for c in cells) / len(cells) if cells else 0.0


def _plumber_tables(
    plumber_page: Any, settings: dict[str, Any], strategy: str, min_rows: int, min_cols: int
) -> list[RawTable]:
    found: list[RawTable] = []
    for t in plumber_page.find_tables(table_settings=settings):
        rows = clean_rows(t.extract())
        if len(rows) < min_rows or max((len(r) for r in rows), default=0) < min_cols:
            continue
        if strategy == "text" and _numeric_density(rows) < 0.2:
            continue  # whitespace "tables" must be numeric; this is prose cut into columns
        x0, top, x1, bottom = t.bbox
        columns, label_header, n_header = header_info(rows)
        found.append(
            RawTable(
                pdf_page=plumber_page.page_number,
                bbox=BBox(x0=x0, top=top, x1=x1, bottom=bottom),
                rows=rows,
                strategy=strategy,
                columns=columns,
                label_header=label_header,
                n_header_rows=n_header,
            )
        )
    return found


_TEXT_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "snap_tolerance": 3,
    "min_words_vertical": 2,
    "min_words_horizontal": 2,
}


def _rebuild_merged(
    pdf_page: int, tables: list[RawTable], words: list[dict[str, Any]]
) -> list[RawTable]:
    """Replace ruled tables whose cells fused several rows by row-by-row statement tables."""
    out: list[RawTable] = []
    for t in tables:
        if t.strategy == "lines" and _has_merged_cells(t.rows):
            inside = [w for w in words if _inside(w, [t.bbox])]
            rebuilt = build_statement_tables(pdf_page, inside)
            if rebuilt:
                out.extend(rebuilt)
                continue
        out.append(t)
    return out


def _is_header_band(t: RawTable) -> bool:
    """A small ruled box holding only text: the column header drawn as its own table."""
    return t.strategy == "lines" and len(t.rows) <= 6 and _money_tokens_total(t.rows) == 0


def _money_tokens_total(rows: list[list[str]]) -> int:
    return sum(_money_tokens(c) for r in rows for c in r)


def _band_feeds(band: RawTable, statement: RawTable) -> bool:
    """Has `statement` absorbed `band` as its header (or does it sit right below it)?"""
    overlap = min(band.bbox.x1, statement.bbox.x1) - max(band.bbox.x0, statement.bbox.x0)
    if overlap <= 0:
        return False
    shared = min(band.bbox.bottom, statement.bbox.bottom) - max(band.bbox.top, statement.bbox.top)
    absorbed = shared >= 0.5 * (band.bbox.bottom - band.bbox.top)
    gap = statement.bbox.top - band.bbox.bottom
    return absorbed or -2.0 <= gap <= 30.0


def _labelless(t: RawTable) -> bool:
    """A table whose first column never holds a word: just numbers, as from a box drawn around the
    value cells of a statement whose row labels lie outside it."""
    return bool(t.rows) and not any(re.search(r"[A-Za-z]{2}", r[0]) for r in t.rows if r)


def _prefer_labelled_statements(
    pdf_page: int,
    words: list[dict[str, Any]],
    data_ruled: list[RawTable],
    statements: list[RawTable],
) -> tuple[list[RawTable], list[RawTable]]:
    """Re-read label-less ruled boxes as part of the unruled statement they sit inside.

    A rectangle around some rows' value cells hides those words from the statement builder, which
    then cuts the statement in pieces (a balance sheet whose total assets and total equity and
    liabilities end up in different tables). If the statement built from all the words outside the
    *other* boxes covers a label-less box, the box was only a drawing: drop it.
    """
    loose = [t for t in data_ruled if _labelless(t)]
    if not loose:
        return data_ruled, statements
    kept = [t for t in data_ruled if t not in loose]
    boxes = [t.bbox for t in kept]
    outside = [w for w in words if not _inside(w, boxes)] if kept else words
    if not looks_numeric_tabular(outside):
        return data_ruled, statements
    rebuilt = build_statement_tables(pdf_page, outside)
    covered = [t for t in loose if any(_overlaps_vertically(t.bbox, st.bbox) for st in rebuilt)]
    if not covered:
        return data_ruled, statements
    return [t for t in data_ruled if t not in covered], rebuilt


def _find_tables(plumber_page: Any, words: list[dict[str, Any]]) -> list[RawTable]:
    """Ruled tables, plus unruled numeric statements among the words outside them.

    A ruled box with no numbers is a header band: if an unruled statement sits right below it, the
    band's words become that statement's header instead of a separate table. On pages with no
    ruled table, pdfplumber's whitespace "text" tables are kept too, unless they overlap a
    rebuilt statement.
    """
    ruled = _rebuild_merged(
        plumber_page.page_number, _plumber_tables(plumber_page, {}, "lines", 2, 2), words
    )
    bands = [t for t in ruled if _is_header_band(t)]
    data_ruled = [t for t in ruled if t not in bands]
    boxes = [t.bbox for t in data_ruled]
    outside = [w for w in words if not _inside(w, boxes)] if data_ruled else words
    if not looks_numeric_tabular(outside):
        return ruled
    statements = build_statement_tables(plumber_page.page_number, outside)
    data_ruled, statements = _prefer_labelled_statements(
        plumber_page.page_number, words, data_ruled, statements
    )
    unused = [b for b in bands if not any(_band_feeds(b, st) for st in statements)]
    if data_ruled or bands:
        return [*data_ruled, *unused, *statements]
    others = _plumber_tables(plumber_page, _TEXT_SETTINGS, "text", 3, 3)
    kept = [
        t for t in others if not any(_overlaps_vertically(t.bbox, st.bbox) for st in statements)
    ]
    return [*statements, *kept]


def _attach_units(tables: list[RawTable], words: list[dict[str, Any]]) -> None:
    """Find a unit caption inside the table's first rows or in the text just above it."""
    for t in tables:
        head_rows = t.rows[: max(t.n_header_rows, 2)]
        header_text = " ".join([*t.columns, t.label_header, *(" ".join(r) for r in head_rows)])
        hit = detect_unit(header_text)
        if hit is None:
            above = [
                w
                for w in words
                if t.bbox.top - UNIT_LOOKBACK <= w["bottom"] <= t.bbox.top + 2
                and w["x1"] >= t.bbox.x0 - 5
            ]
            text = " ".join(w["text"] for ln in _group_lines(above) for w in ln)
            hit = detect_unit(text)
        if hit:
            t.unit, t.unit_text = hit
            continue
        # e.g. KPI tables that put the unit in each row label: "EBITDA (Rs. in Lakhs)"
        row_hits = [h for r in t.rows if r and (h := detect_unit(r[0]))]
        if row_hits and len({h[0] for h in row_hits}) == 1:
            t.unit, t.unit_text = row_hits[0][0], f"row labels: {row_hits[0][1]}"


def _parse_one_page(pdfium_doc: Any, raw_page: Any, n: int) -> ParsedPage:
    visible_page, hidden_removed, invisible = _hidden_text(raw_page)
    plumber_page = _without_overlapping_spaces(visible_page)
    words = plumber_page.extract_words(keep_blank_chars=False, use_text_flow=False)
    n_images, coverage = _page_image_stats(pdfium_doc[n - 1])
    alnum = sum(ch.isalnum() for w in words for ch in w["text"])

    tables = _find_tables(plumber_page, words)
    _attach_units(tables, words)
    height = float(raw_page.height)
    return ParsedPage(
        pdf_page=n,
        printed_page=_printed_page(words, height),
        width=float(raw_page.width),
        height=height,
        alnum_chars=alnum,
        n_images=n_images,
        image_coverage=coverage,
        needs_ocr=alnum < MIN_ALNUM_FOR_TEXT_LAYER and n_images > 0,
        blocks=_blocks_from_words(n, words, [t.bbox for t in tables]),
        tables=tables,
        hidden_chars_removed=hidden_removed,
        invisible_chars=invisible,
    )


def _parse_pages(path: str, page_numbers: list[int]) -> list[ParsedPage]:
    """Parse the given 1-based pages. Top-level so it can run in a worker process."""
    pdfium_doc = pdfium.PdfDocument(path)
    out: list[ParsedPage] = []
    try:
        with pdfplumber.open(path) as plumber:
            for n in page_numbers:
                raw_page = plumber.pages[n - 1]
                try:
                    out.append(_parse_one_page(pdfium_doc, raw_page, n))
                except Exception as exc:  # one bad page must not lose the document
                    out.append(
                        ParsedPage(
                            pdf_page=n,
                            width=float(raw_page.width),
                            height=float(raw_page.height),
                            alnum_chars=0,
                            n_images=0,
                            image_coverage=0.0,
                            needs_ocr=False,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )
                finally:
                    raw_page.flush_cache()
    finally:
        pdfium_doc.close()
    return out


def default_workers() -> int:
    return max(1, min(4, os.cpu_count() or 1))


def parse_pdf(
    path: Path,
    *,
    doc_id: str | None = None,
    sha256: str | None = None,
    pages: range | None = None,
    workers: int = 1,
    min_pages_per_worker: int = 40,
) -> ParsedDocument:
    """Parse `path`. `pages` is a range of 1-based PDF pages (default: all).

    With `workers` > 1 the pages are split into contiguous chunks parsed in separate processes
    (pdfplumber is pure Python and CPU-bound); results are identical to the serial run.
    """
    started = time.perf_counter()
    pdfium_doc = pdfium.PdfDocument(str(path))
    try:
        n_pages = len(pdfium_doc)
    finally:
        pdfium_doc.close()
    selected = list(pages if pages is not None else range(1, n_pages + 1))
    n_workers = max(1, min(workers, len(selected) // max(min_pages_per_worker, 1)))
    if n_workers <= 1:
        parsed_pages = _parse_pages(str(path), selected)
    else:
        size = -(-len(selected) // n_workers)
        chunks = [selected[i : i + size] for i in range(0, len(selected), size)]
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            results = list(pool.map(_parse_pages, [str(path)] * len(chunks), chunks))
        parsed_pages = [p for chunk in results for p in chunk]

    heights = {p.pdf_page: p.height for p in parsed_pages}
    raw_tables = [t for p in parsed_pages for t in p.tables]
    inherit_headers(raw_tables)
    inherit_units(raw_tables)
    return ParsedDocument(
        doc_id=doc_id or path.stem,
        sha256=sha256,
        parser_version=PARSER_VERSION,
        n_pages=n_pages,
        parse_seconds=round(time.perf_counter() - started, 2),
        pages=parsed_pages,
        tables=stitch_tables(raw_tables, heights),
    )
