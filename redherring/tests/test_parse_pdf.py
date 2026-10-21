from pathlib import Path

import pytest

from redherring.parse.pdf import parse_pdf
from redherring.parse.render import render_tagged
from redherring.parse.report import compute_stats
from redherring.parse.units import Unit
from tests.pdfgen import PageSpec, build_pdf

HEADER = ["Particulars", "FY 2024", "FY 2023"]


@pytest.fixture(scope="module")
def synthetic_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    p1 = PageSpec()
    p1.text(72, 80, "RISK FACTORS", 14)
    p1.text(72, 110, "Internal risk factors relating to our business.", 10)
    p1.text(72, 124, "We depend on a limited number of customers.", 10)
    p1.text(72, 190, "A second paragraph begins here after a gap.", 10)
    p1.text(300, 760, "iii", 9)  # printed page number differs from PDF page 1

    p2 = PageSpec()
    p2.text(72, 60, "Restated Summary Statement", 12)
    p2.text(72, 78, "(₹ in lakhs)".replace("₹", "Rs."), 9)
    p2.grid(72, 95, [200, 100, 100], [HEADER, ["Revenue", "1,000", "900"], ["PAT", "(50)", "40"]])
    p2.text(300, 760, "2", 9)

    # Table that runs across pages 3 -> 4 with a repeated header.
    p3 = PageSpec().text(72, 604, "Balance sheet (Rs. in million)", 10)
    rows3 = [HEADER] + [[f"Item {i}", str(i * 10), str(i * 9)] for i in range(1, 8)]
    p3.grid(72, 630, [200, 100, 100], rows3[:8], row_h=18)
    p4 = PageSpec()
    rows4 = [HEADER, ["Item 8", "80", "72"], ["Item 9", "90", "81"]]
    p4.grid(72, 40, [200, 100, 100], rows4, row_h=18)

    p5 = PageSpec().image()  # image-only: scanned-style page, no text layer

    path = tmp_path_factory.mktemp("pdf") / "synthetic.pdf"
    path.write_bytes(build_pdf([p1, p2, p3, p4, p5]))
    return path


def test_pages_and_tags(synthetic_pdf: Path) -> None:
    doc = parse_pdf(synthetic_pdf, doc_id="syn")
    assert doc.n_pages == 5
    assert [p.pdf_page for p in doc.pages] == [1, 2, 3, 4, 5]
    tagged = render_tagged(doc)
    for n in range(1, 6):
        assert f"[PDF_PAGE_{n}]" in tagged
    assert (
        tagged.index("[PDF_PAGE_1]") < tagged.index("RISK FACTORS") < tagged.index("[PDF_PAGE_2]")
    )


def test_printed_page_is_separate_from_pdf_page(synthetic_pdf: Path) -> None:
    doc = parse_pdf(synthetic_pdf)
    assert doc.pages[0].pdf_page == 1
    assert doc.pages[0].printed_page == "iii"
    assert doc.pages[1].printed_page == "2"


def test_blocks_split_on_vertical_gap(synthetic_pdf: Path) -> None:
    doc = parse_pdf(synthetic_pdf)
    texts = [b.text for b in doc.pages[0].blocks]
    assert any("Internal risk factors" in t and "limited number of customers" in t for t in texts)
    assert any(t.startswith("A second paragraph") for t in texts)
    assert all(b.pdf_page == 1 for b in doc.pages[0].blocks)


def test_ruled_table_with_unit_caption(synthetic_pdf: Path) -> None:
    doc = parse_pdf(synthetic_pdf)
    (raw,) = doc.pages[1].tables
    assert raw.rows[1] == ["Revenue", "1,000", "900"]
    assert raw.unit is Unit.LAKH
    # table cells must not also appear as prose
    assert not any("Revenue" in b.text for b in doc.pages[1].blocks)


def test_multi_page_table_is_stitched(synthetic_pdf: Path) -> None:
    doc = parse_pdf(synthetic_pdf)
    stitched = [t for t in doc.tables if t.stitched_from > 1]
    assert len(stitched) == 1
    t = stitched[0]
    assert t.pdf_pages == [3, 4]
    assert t.unit is Unit.MILLION
    labels = [r[0] for r in t.rows]
    assert labels.count("Particulars") == 1  # repeated header removed
    assert labels[-1] == "Item 9"


def test_image_only_page_flagged_for_ocr(synthetic_pdf: Path) -> None:
    doc = parse_pdf(synthetic_pdf)
    assert [p.needs_ocr for p in doc.pages] == [False, False, False, False, True]
    assert doc.pages[4].image_coverage > 0.5
    assert "[NO_TEXT_LAYER" in render_tagged(doc, pages=[5])


def test_page_subset(synthetic_pdf: Path) -> None:
    doc = parse_pdf(synthetic_pdf, pages=range(2, 3))
    assert [p.pdf_page for p in doc.pages] == [2]
    assert doc.n_pages == 5


def test_stats(synthetic_pdf: Path) -> None:
    stats = compute_stats(parse_pdf(synthetic_pdf, doc_id="syn"))
    assert stats.n_pages == 5
    assert stats.pages_needs_ocr == 1
    assert stats.pct_needs_ocr == 20.0
    assert stats.multi_page_tables == 1
    assert stats.tables_with_unit == stats.logical_tables
