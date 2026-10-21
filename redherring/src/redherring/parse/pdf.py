"""PDF -> page-tagged blocks and tables.

pypdfium2 (fast) answers "does this page have a text layer / images?"; pdfplumber supplies word
geometry and table finding. Both are permissively licensed. No OCR happens here: pages with no
text layer but images are flagged `needs_ocr` so scanned content is reported, not silently lost.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pdfplumber
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from redherring.parse.models import BBox, Block, ParsedDocument, ParsedPage, RawTable
from redherring.parse.tables import clean_rows, stitch_tables
from redherring.parse.units import detect_unit

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


def _group_lines(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    lines: list[list[dict[str, Any]]] = []
    for w in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= LINE_TOL:
            lines[-1].append(w)
        else:
            lines.append([w])
    for line in lines:
        line.sort(key=lambda w: w["x0"])
    return lines


def _line_bbox(line: list[dict[str, Any]]) -> BBox:
    return BBox(
        x0=min(w["x0"] for w in line),
        top=min(w["top"] for w in line),
        x1=max(w["x1"] for w in line),
        bottom=max(w["bottom"] for w in line),
    )


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


def _looks_numeric_tabular(words: list[dict[str, Any]]) -> bool:
    numeric = re.compile(r"^\(?[\d,]+(?:\.\d+)?\)?%?$")
    rows_with_numbers = 0
    for line in _group_lines(words):
        if sum(bool(numeric.match(w["text"])) for w in line) >= 2:
            rows_with_numbers += 1
    return rows_with_numbers >= 4


def _find_tables(plumber_page: Any, words: list[dict[str, Any]]) -> list[RawTable]:
    found: list[RawTable] = []
    for strategy, settings in (
        ("lines", {}),
        (
            "text",
            {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "snap_tolerance": 3,
                "min_words_vertical": 2,
                "min_words_horizontal": 2,
            },
        ),
    ):
        if strategy == "text" and (found or not _looks_numeric_tabular(words)):
            break
        for t in plumber_page.find_tables(table_settings=settings):
            rows = clean_rows(t.extract())
            min_rows, min_cols = (2, 2) if strategy == "lines" else (3, 3)
            if len(rows) < min_rows or max((len(r) for r in rows), default=0) < min_cols:
                continue
            x0, top, x1, bottom = t.bbox
            found.append(
                RawTable(
                    pdf_page=plumber_page.page_number,
                    bbox=BBox(x0=x0, top=top, x1=x1, bottom=bottom),
                    rows=rows,
                    strategy=strategy,
                )
            )
    return found


def _attach_units(tables: list[RawTable], words: list[dict[str, Any]]) -> None:
    """Find a unit caption inside the table's first rows or in the text just above it."""
    for t in tables:
        header_text = " ".join(" ".join(r) for r in t.rows[:2])
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


def parse_pdf(
    path: Path,
    *,
    doc_id: str | None = None,
    sha256: str | None = None,
    pages: range | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> ParsedDocument:
    """Parse `path`. `pages` is a range of 1-based PDF pages (default: all)."""
    started = time.perf_counter()
    pdfium_doc = pdfium.PdfDocument(str(path))
    parsed_pages: list[ParsedPage] = []
    raw_tables: list[RawTable] = []
    heights: dict[int, float] = {}
    try:
        with pdfplumber.open(path) as plumber:
            n_pages = len(plumber.pages)
            selected = pages if pages is not None else range(1, n_pages + 1)
            for n in selected:
                plumber_page = plumber.pages[n - 1]
                width, height = float(plumber_page.width), float(plumber_page.height)
                heights[n] = height

                words = plumber_page.extract_words(keep_blank_chars=False, use_text_flow=False)
                n_images, coverage = _page_image_stats(pdfium_doc[n - 1])
                alnum = sum(ch.isalnum() for w in words for ch in w["text"])

                tables = _find_tables(plumber_page, words)
                _attach_units(tables, words)
                blocks = _blocks_from_words(n, words, [t.bbox for t in tables])

                parsed_pages.append(
                    ParsedPage(
                        pdf_page=n,
                        printed_page=_printed_page(words, height),
                        width=width,
                        height=height,
                        alnum_chars=alnum,
                        n_images=n_images,
                        image_coverage=coverage,
                        needs_ocr=alnum < MIN_ALNUM_FOR_TEXT_LAYER and n_images > 0,
                        blocks=blocks,
                        tables=tables,
                    )
                )
                raw_tables.extend(tables)
                plumber_page.flush_cache()
                if progress:
                    progress(n, n_pages)
    finally:
        pdfium_doc.close()

    return ParsedDocument(
        doc_id=doc_id or path.stem,
        sha256=sha256,
        n_pages=n_pages,
        parse_seconds=round(time.perf_counter() - started, 2),
        pages=parsed_pages,
        tables=stitch_tables(raw_tables, heights),
    )
