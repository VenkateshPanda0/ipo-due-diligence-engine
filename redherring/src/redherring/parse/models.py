"""Parse-layer data model. Everything carries a 1-based PDF page index (`pdf_page`).

`pdf_page` is the physical page in the PDF file, never the number printed on the page
(`printed_page`), which is only recorded for reference.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from redherring.parse.units import Unit

# Bump whenever parser output changes meaningfully; cached parsed files with another version
# are re-parsed. 1: initial. 2: overlap-space fix, numeric_rows, row-label units, no row flipping.
# 3: x-anchored statement columns with assembled headers, residual rows beside ruled tables.
# 4: ruled boxes with fused cells are rebuilt row by row; prose is not a text table.
# 5: column headers for ruled tables and for headers separated by label-only lines.
PARSER_VERSION = 5


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
    strategy: str  # "lines" (ruled), "numeric_rows" (unruled statement) or "text"
    unit: Unit | None = None
    unit_text: str | None = None
    # numeric_rows only: header text per value column (rows are [label, *values] in that order)
    # and the header text over the label column.
    columns: list[str] = Field(default_factory=list)
    label_header: str = ""
    # ruled/text tables: how many leading rows of `rows` are header rows (already folded into
    # `columns`/`label_header`, but left in `rows` as found). numeric_rows tables have none.
    n_header_rows: int = 0


class Table(BaseModel):
    """A logical table, possibly stitched from several consecutive pages."""

    pdf_pages: list[int]
    rows: list[list[str]]
    unit: Unit | None = None
    unit_text: str | None = None
    columns: list[str] = Field(default_factory=list)  # see RawTable.columns
    label_header: str = ""
    n_header_rows: int = 0
    # True if periods appear to run down the first column. `rows` are kept AS FOUND; the flag is
    # unvalidated (see M0 report) so nothing is flipped silently. Use `tables.transpose` to flip.
    transposed_suspect: bool = False
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
    error: str | None = Field(default=None, description="Set if this page failed to parse")


class ParsedDocument(BaseModel):
    doc_id: str
    sha256: str | None = None
    parser_version: int = 0  # 0 = written before versioning; always treated as stale
    n_pages: int
    parse_seconds: float = 0.0
    pages: list[ParsedPage]
    tables: list[Table] = Field(default_factory=list)
