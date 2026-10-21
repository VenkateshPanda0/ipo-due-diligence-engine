"""Parse-layer data model. Everything carries a 1-based PDF page index (`pdf_page`).

`pdf_page` is the physical page in the PDF file, never the number printed on the page
(`printed_page`), which is only recorded for reference.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from redherring.parse.units import Unit


def page_tag(pdf_page: int) -> str:
    return f"[PDF_PAGE_{pdf_page}]"


class BBox(BaseModel):
    """Page coordinates in PDF points, origin top-left."""

    x0: float
    top: float
    x1: float
    bottom: float


class Block(BaseModel):
    pdf_page: int
    bbox: BBox
    text: str


class RawTable(BaseModel):
    """A table as found on a single page, before multi-page stitching."""

    pdf_page: int
    bbox: BBox
    rows: list[list[str]]
    strategy: str  # "lines" (ruled) or "text" (whitespace-aligned fallback)
    unit: Unit | None = None
    unit_text: str | None = None


class Table(BaseModel):
    """A logical table, possibly stitched from several consecutive pages."""

    pdf_pages: list[int]
    rows: list[list[str]]
    unit: Unit | None = None
    unit_text: str | None = None
    transposed: bool = False  # True if `rows` were transposed so periods are columns
    stitched_from: int = 1


class ParsedPage(BaseModel):
    pdf_page: int
    printed_page: str | None = None
    width: float
    height: float
    alnum_chars: int
    n_images: int
    image_coverage: float = Field(description="Fraction of page area covered by images, 0..1")
    needs_ocr: bool = Field(description="Little/no text layer but page contains images")
    blocks: list[Block] = Field(default_factory=list)
    tables: list[RawTable] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    doc_id: str
    sha256: str | None = None
    n_pages: int
    parse_seconds: float = 0.0
    pages: list[ParsedPage]
    tables: list[Table] = Field(default_factory=list)
