"""Render a ParsedDocument as page-tagged plain text, the form fed to downstream extractors.

Page numbers come from parser metadata only (`[PDF_PAGE_N]`), never from text on the page.
Document text is data: nothing here interprets it.
"""

from __future__ import annotations

from collections.abc import Iterable

from redherring.parse.models import ParsedDocument, page_tag


def render_tagged(doc: ParsedDocument, pages: Iterable[int] | None = None) -> str:
    wanted = set(pages) if pages is not None else None
    out: list[str] = []
    for page in doc.pages:
        if wanted is not None and page.pdf_page not in wanted:
            continue
        out.append(page_tag(page.pdf_page))
        if page.needs_ocr:
            out.append("[NO_TEXT_LAYER: page needs OCR]")
        out.extend(b.text for b in page.blocks)
        for t in page.tables:
            unit = f" unit={t.unit.value}" if t.unit else ""
            out.append(f"[TABLE pdf_page={t.pdf_page} strategy={t.strategy}{unit}]")
            out.extend(" | ".join(r) for r in t.rows)
            out.append("[/TABLE]")
    return "\n".join(out)
