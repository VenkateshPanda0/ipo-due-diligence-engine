"""
Synthetic offer-document PDFs for document-intelligence tests.

These are SYNTHETIC fixtures. They exercise layouts and formatting conditions;
they are not real-world validation (see docs/BENCHMARK.md for real documents).
"""

from __future__ import annotations

import io
import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PAGE_W, PAGE_H = A4


@dataclass
class TableSpec:
    caption: str
    unit_text: str | None
    headers: Sequence[str]
    rows: Sequence[tuple[str, Sequence[str]]]
    basis_title: str | None = None
    show_header: bool = True


@dataclass
class PageSpec:
    lines: Sequence[str] = ()
    table: TableSpec | None = None
    landscape: bool = False
    rotate_content: bool = False  # draw text rotated 90° (sideways table)
    table_top: float | None = None  # y position for the table (points from bottom)


@dataclass
class DocSpec:
    pages: list[PageSpec] = field(default_factory=list)


def eligibility_table(
    unit_text: str | None = "(₹ in lakhs)",
    values: dict[str, Sequence[str]] | None = None,
    headers: Sequence[str] = (
        "As at March 31, 2024",
        "As at March 31, 2023",
        "As at March 31, 2022",
    ),
    basis: str = "Restated Consolidated",
) -> TableSpec:
    vals = values or {
        "Net tangible assets, as restated": ("12,345.67", "9,876.54", "7,654.32"),
        "Monetary assets, as restated": ("1,234.56", "987.65", "765.43"),
        "Monetary assets as a % of net tangible assets": ("10.00%", "10.00%", "10.00%"),
        "Operating profit, as restated": ("3,210.00", "2,100.50", "1,950.25"),
        "Net worth, as restated": ("15,000.00", "12,000.00", "10,000.00"),
    }
    return TableSpec(
        caption=f"Eligibility for the Offer — {basis} financial information",
        unit_text=unit_text,
        headers=headers,
        rows=list(vals.items()),
        basis_title=f"{basis} Statement",
    )


def _draw_table(
    c: canvas.Canvas, t: TableSpec, y: float, x_label: float = 50, col_w: float = 115
) -> float:
    if not t.show_header:
        c.setFont("Helvetica", 9)
        for label, values in t.rows:
            c.drawString(x_label, y, label)
            for i, v in enumerate(values):
                c.drawRightString(x_label + 220 + col_w * (i + 1), y, v)
            y -= 16
        return y
    c.setFont("Helvetica-Bold", 10)
    if t.basis_title:
        c.drawString(x_label, y, t.basis_title)
        y -= 16
    c.drawString(x_label, y, t.caption)
    y -= 16
    c.setFont("Helvetica", 9)
    if t.unit_text:
        c.drawRightString(PAGE_W - 40, y, t.unit_text)
        y -= 16
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x_label, y, "Particulars")
    for i, h in enumerate(t.headers):
        c.drawRightString(x_label + 220 + col_w * (i + 1), y, h)
    y -= 18
    c.setFont("Helvetica", 9)
    for label, values in t.rows:
        c.drawString(x_label, y, label)
        for i, v in enumerate(values):
            c.drawRightString(x_label + 220 + col_w * (i + 1), y, v)
        y -= 16
    return y


def build_pdf(spec: DocSpec) -> bytes:
    """Render a DocSpec to native-text PDF bytes."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for page in spec.pages:
        size = landscape(A4) if page.landscape else A4
        c.setPageSize(size)
        if page.rotate_content:
            c.translate(size[0], 0)
            c.rotate(90)
        y = (size[0] if page.rotate_content else size[1]) - 60
        c.setFont("Helvetica", 10)
        for line in page.lines:
            c.drawString(50, y, line)
            y -= 14
        if page.table is not None:
            _draw_table(c, page.table, page.table_top if page.table_top is not None else y - 10)
        c.showPage()
    c.save()
    return buf.getvalue()


def rasterize(
    pdf_bytes: bytes,
    *,
    dpi: int = 150,
    skew_deg: float = 0.0,
    noise: float = 0.0,
    blur: float = 0.0,
    rotate: int = 0,
    seed: int = 7,
) -> bytes:
    """Turn every page into an image-only page (simulated scan)."""
    import pypdfium2 as pdfium

    rng = random.Random(seed)
    doc = pdfium.PdfDocument(pdf_bytes)
    images: list[Image.Image] = []
    for i in range(len(doc)):
        img = doc[i].render(scale=dpi / 72).to_pil().convert("L")
        if noise:
            px = img.load()
            for _ in range(int(img.width * img.height * noise)):
                px[rng.randrange(img.width), rng.randrange(img.height)] = rng.choice((0, 255))
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        if skew_deg:
            img = img.rotate(skew_deg, expand=True, fillcolor=255)
        if rotate:
            img = img.rotate(rotate, expand=True, fillcolor=255)
        images.append(img.convert("RGB"))
    doc.close()
    out = io.BytesIO()
    images[0].save(out, format="PDF", save_all=True, append_images=images[1:], resolution=dpi)
    return out.getvalue()


def text_image_pdf(lines: Sequence[str], *, dpi: int = 150) -> bytes:
    """An image-only PDF with the given text lines (no native text at all)."""
    w, h = int(8.27 * dpi), int(11.69 * dpi)
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(dpi * 0.14))
    y = int(dpi * 0.8)
    for line in lines:
        draw.text((int(dpi * 0.7), y), line, fill="black", font=font)
        y += int(dpi * 0.25)
    out = io.BytesIO()
    img.save(out, format="PDF", resolution=dpi)
    return out.getvalue()


def standard_drhp(
    *,
    unit_text: str | None = "(₹ in lakhs)",
    values: dict[str, Sequence[str]] | None = None,
    headers: Sequence[str] = (
        "As at March 31, 2024",
        "As at March 31, 2023",
        "As at March 31, 2022",
    ),
    extra_pages: Sequence[PageSpec] = (),
) -> bytes:
    """A small DRHP-like document with cover, eligibility table and declarations."""
    cover = PageSpec(
        lines=[
            "DRAFT RED HERRING PROSPECTUS",
            "ACME INDUSTRIES LIMITED",
            "Initial public offering through the Book Building Process consisting of a Fresh Issue",
            "and an Offer for Sale of equity shares.",
        ]
    )
    eligibility = PageSpec(
        lines=[
            "OTHER REGULATORY AND STATUTORY DISCLOSURES",
            "Our Company is eligible for the Offer in accordance with "
            "Regulation 6(1) of the SEBI ICDR",
            "Regulations, as set out below:",
        ],
        table=eligibility_table(unit_text, values, headers),
    )
    declarations = PageSpec(
        lines=[
            "Prohibition by SEBI or other Governmental Authorities",
            "Our Company, our Promoters, members of the Promoter Group and our Directors "
            "are not prohibited",
            "from accessing the capital market or debarred from buying, selling or dealing "
            "in securities.",
            "Neither our Company, nor our Promoters or Directors have been identified as "
            "wilful defaulters",
            "or fraudulent borrowers.",
            "None of our Promoters or Directors have been declared as fugitive economic offenders.",
        ]
    )
    return build_pdf(DocSpec([cover, eligibility, declarations, *extra_pages]))


def split_table_drhp() -> bytes:
    """Eligibility table whose last rows continue on the next page without a header."""
    full = eligibility_table()
    first = TableSpec(
        full.caption, full.unit_text, full.headers, list(full.rows)[:2], full.basis_title
    )
    rest = TableSpec(full.caption, None, full.headers, list(full.rows)[2:], show_header=False)
    filler = [f"Paragraph {i}: narrative disclosure text without figures." for i in range(30)]
    return build_pdf(
        DocSpec(
            [
                PageSpec(lines=["DRAFT RED HERRING PROSPECTUS", "Book Building Process"]),
                PageSpec(lines=filler, table=first, table_top=150),
                PageSpec(table=rest, table_top=PAGE_H - 60),
            ]
        )
    )
