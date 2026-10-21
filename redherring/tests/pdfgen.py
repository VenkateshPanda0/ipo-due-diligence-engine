"""Minimal PDF writer for tests (Helvetica text, ruled grids, one raster image).

Coordinates are given from the top-left of a 612x792 page, like pdfplumber reports them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PAGE_W, PAGE_H = 612, 792


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


@dataclass
class PageSpec:
    ops: list[str] = field(default_factory=list)
    has_image: bool = False

    def text(self, x: float, top: float, s: str, size: float = 10) -> PageSpec:
        y = PAGE_H - top - size
        self.ops.append(f"BT /F1 {size} Tf {x} {y} Td ({_esc(s)}) Tj ET")
        return self

    def grid(
        self,
        x: float,
        top: float,
        col_w: list[float],
        rows: list[list[str]],
        row_h: float = 18,
        size: float = 9,
    ) -> PageSpec:
        for r, row in enumerate(rows):
            cx = x
            for c, cell in enumerate(row):
                cy = top + r * row_h
                self.ops.append(f"{cx} {PAGE_H - cy - row_h} {col_w[c]} {row_h} re S")
                self.text(cx + 3, cy + 4, cell, size)
                cx += col_w[c]
        return self

    def image(self) -> PageSpec:
        self.has_image = True
        self.ops.append(f"q {PAGE_W - 100} 0 0 {PAGE_H - 100} 50 50 cm /Im1 Do Q")
        return self


def build_pdf(pages: list[PageSpec]) -> bytes:
    objs: list[bytes] = []

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    add(b"<< /Type /Catalog /Pages 2 0 R >>")  # 1
    add(b"")  # 2 (pages) placeholder
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    img_data = bytes([0, 255, 255, 0])
    image = add(
        b"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray "
        b"/BitsPerComponent 8 /Length 4 >>\nstream\n" + img_data + b"\nendstream"
    )
    kids: list[int] = []
    for p in pages:
        stream = "\n".join(p.ops).encode("latin-1")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        xobj = f"/XObject << /Im1 {image} 0 R >>" if p.has_image else ""
        page = add(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Contents {content} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> {xobj} >> >>".encode()
        )
        kids.append(page)
    kid_refs = " ".join(f"{k} 0 R" for k in kids)
    objs[1] = f"<< /Type /Pages /Kids [{kid_refs}] /Count {len(kids)} >>".encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
