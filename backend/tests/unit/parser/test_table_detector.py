from __future__ import annotations

from app.parser.table_detector import TableDetector


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


def test_table_detector_extracts_pipe_delimited_rows() -> None:
    detector = TableDetector()

    tables = detector.extract_tables_from_text("| FY | Revenue |\n| FY2024 | 100 |", page_number=3)

    assert len(tables) == 1
    assert tables[0].page_number == 3
    assert tables[0].rows[1] == ["FY2024", "100"]


def test_table_detector_returns_empty_when_no_table() -> None:
    assert TableDetector().extract_tables_from_text("plain text") == []


def test_table_detector_extracts_pdf_tables_with_page_numbers() -> None:
    detector = TableDetector()
    pdf = _minimal_pdf(
        "0.5 w\n"
        "72 620 m 300 620 l S\n"
        "72 590 m 300 590 l S\n"
        "72 560 m 300 560 l S\n"
        "72 620 m 72 560 l S\n"
        "140 620 m 140 560 l S\n"
        "220 620 m 220 560 l S\n"
        "300 620 m 300 560 l S\n"
        "BT /F1 10 Tf 80 600 Td (FY) Tj 70 0 Td (Revenue) Tj 80 0 Td (PAT) Tj ET\n"
        "BT /F1 10 Tf 80 570 Td (FY2024) Tj 70 0 Td (100) Tj 80 0 Td (10) Tj ET\n"
    )

    tables = detector.extract_tables_from_pdf(pdf)

    assert len(tables) == 1
    assert tables[0].page_number == 1
    assert tables[0].extraction_method == "pdfplumber"
    assert tables[0].rows == [["FY", "Revenue", "PAT"], ["FY2024", "100", "10"]]
