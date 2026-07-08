from __future__ import annotations

from app.parser.pdf_parser import PDFParser


def _minimal_pdf(content_stream: str) -> bytes:
    objects: list[tuple[int, bytes]] = []

    def add_object(number: int, content: str) -> None:
        objects.append((number, content.encode("latin-1")))

    stream = content_stream.encode("latin-1")
    add_object(1, "<< /Type /Catalog /Pages 2 0 R >>")
    add_object(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    add_object(
        3,
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    )
    add_object(4, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    add_object(5, f"<< /Length {len(stream)} >>\nstream\n{content_stream}\nendstream")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, content in objects:
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("latin-1"))
        pdf.extend(content)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\n"
        f"startxref\n{xref_offset}\n%%EOF".encode("latin-1")
    )
    return bytes(pdf)


def test_pdf_parser_extracts_text_pages_from_bytes() -> None:
    parser = PDFParser()

    pages = parser.extract_text(b"first page\fsecond page")

    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert pages[1].text == "second page"


def test_pdf_parser_extracts_text_from_real_pdf_binary() -> None:
    parser = PDFParser()
    content = _minimal_pdf("BT /F1 12 Tf 72 720 Td (Draft Red Herring Prospectus) Tj ET")

    pages = parser.extract_text(content)

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "Draft Red Herring Prospectus" in pages[0].text


def test_pdf_parser_uses_ocr_for_poor_quality_pdf_text() -> None:
    class FakeOCR:
        def extract_page_text(self, _content: bytes, page_number: int) -> str:
            return f"OCR text from page {page_number}"

    parser = PDFParser(ocr_engine=FakeOCR())  # type: ignore[arg-type]
    content = _minimal_pdf("BT /F1 12 Tf 72 720 Td (Hi) Tj ET")

    pages = parser.extract_text(content)

    assert pages[0].text == "OCR text from page 1"


def test_pdf_parser_assesses_text_quality() -> None:
    parser = PDFParser()

    assert parser.assess_quality("Draft Red Herring Prospectus content").is_usable
    assert not parser.assess_quality("").is_usable
