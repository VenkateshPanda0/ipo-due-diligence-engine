"""Parse-quality statistics: what the parser found, and what it could not."""

from __future__ import annotations

from pydantic import BaseModel

from redherring.parse.models import ParsedDocument


class ParseStats(BaseModel):
    doc_id: str
    n_pages: int
    parse_seconds: float
    pages_no_text_layer: int  # alnum chars below threshold (includes blank pages)
    pages_needs_ocr: int  # no text layer and has images
    pct_needs_ocr: float
    blocks: int
    raw_tables: int
    logical_tables: int
    multi_page_tables: int
    transposed_tables: int
    tables_with_unit: int
    pct_tables_with_unit: float
    pages_with_printed_number: int


def compute_stats(doc: ParsedDocument) -> ParseStats:
    from redherring.parse.pdf import MIN_ALNUM_FOR_TEXT_LAYER

    n = max(len(doc.pages), 1)
    needs_ocr = sum(p.needs_ocr for p in doc.pages)
    with_unit = sum(t.unit is not None for t in doc.tables)
    return ParseStats(
        doc_id=doc.doc_id,
        n_pages=doc.n_pages,
        parse_seconds=doc.parse_seconds,
        pages_no_text_layer=sum(p.alnum_chars < MIN_ALNUM_FOR_TEXT_LAYER for p in doc.pages),
        pages_needs_ocr=needs_ocr,
        pct_needs_ocr=round(100 * needs_ocr / n, 1),
        blocks=sum(len(p.blocks) for p in doc.pages),
        raw_tables=sum(len(p.tables) for p in doc.pages),
        logical_tables=len(doc.tables),
        multi_page_tables=sum(t.stitched_from > 1 for t in doc.tables),
        transposed_tables=sum(t.transposed for t in doc.tables),
        tables_with_unit=with_unit,
        pct_tables_with_unit=round(100 * with_unit / max(len(doc.tables), 1), 1),
        pages_with_printed_number=sum(p.printed_page is not None for p in doc.pages),
    )


def stats_markdown(rows: list[ParseStats]) -> str:
    cols = [
        ("doc_id", "doc"),
        ("n_pages", "pages"),
        ("parse_seconds", "sec"),
        ("pages_needs_ocr", "OCR pages"),
        ("pct_needs_ocr", "% OCR"),
        ("blocks", "blocks"),
        ("raw_tables", "raw tbl"),
        ("logical_tables", "logical tbl"),
        ("multi_page_tables", "multi-pg"),
        ("transposed_tables", "transposed"),
        ("pct_tables_with_unit", "% tbl w/ unit"),
        ("pages_with_printed_number", "printed pg #"),
    ]
    lines = ["| " + " | ".join(h for _, h in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        d = r.model_dump()
        lines.append("| " + " | ".join(str(d[k]) for k, _ in cols) + " |")
    return "\n".join(lines)
