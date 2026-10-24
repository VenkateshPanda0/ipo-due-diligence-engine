from pathlib import Path

import pytest

from redherring.parse.models import ParsedDocument
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


def _statement_pdf(tmp_path: Path) -> Path:
    """Unruled, right-aligned financial statement, with padding spaces overlapping first digits."""
    p = PageSpec()
    p.text(72, 60, "Annexure VI: Notes to Restated Consolidated Summary Statements", 10)
    p.text(72, 74, "(All amounts are in Indian Rupees in Million, except as stated otherwise)", 8)
    p.text(72, 96, "Particulars", 8)
    p.text(330, 96, "March 31, 2025", 8)
    p.text(430, 96, "March 31, 2024", 8)
    rows = [
        ("Revenue from operations", "1,000.50", "900.25"),
        ("Other income", "12.75", "9.10"),
        ("Total income", "1,013.25", "909.35"),
        ("Profit before tax", "(50.00)", "40.00"),
        ("Cash and cash equivalents", "9,521.29", "4,871.75"),
    ]
    for i, (label, a, b) in enumerate(rows):
        top = 114 + i * 14
        p.text(72, top, label, 8)
        p.text(400 - 4.45 * len(a), top, a, 8)
        p.text(500 - 4.45 * len(b), top, b, 8)
    # One value emitted the way the Moneyview PDF does: first digit, an overlapping space, rest.
    p.text(72, 190, "Deposits with banks", 10)
    p.text(344.0, 190, "7", 10)  # Helvetica digit is 5.56 pt wide at 10 pt
    p.text(345.0, 190, " ", 10)  # padding space sitting on top of the "7"
    p.text(349.56, 190, ",654.32", 10)
    path = tmp_path / "statement.pdf"
    path.write_bytes(build_pdf([p]))
    return path


def test_space_overlapping_a_digit_does_not_split_the_number(tmp_path: Path) -> None:
    doc = parse_pdf(_statement_pdf(tmp_path))
    all_text = " ".join(" ".join(r) for t in doc.pages[0].tables for r in t.rows) + " ".join(
        b.text for b in doc.pages[0].blocks
    )
    assert "7,654.32" in all_text
    assert "7 ,654.32" not in all_text


def test_unruled_numeric_statement_becomes_rows_with_unit(tmp_path: Path) -> None:
    doc = parse_pdf(_statement_pdf(tmp_path))
    tables = [t for t in doc.pages[0].tables if t.strategy == "numeric_rows"]
    assert len(tables) == 1
    t = tables[0]
    assert ["Revenue from operations", "1,000.50", "900.25"] in t.rows
    assert ["Profit before tax", "(50.00)", "40.00"] in t.rows
    assert t.unit is Unit.MILLION
    # the statement lines are in the table, not duplicated as prose
    assert not any("Revenue from operations" in b.text for b in doc.pages[0].blocks)


def test_unit_inside_row_labels(tmp_path: Path) -> None:
    p = PageSpec()
    rows = [
        ["Particulars", "FY 2024", "FY 2023"],
        ["Number of customers", "120", "95"],
        ["Revenue from Operations (Rs. in Lakhs)", "1718.99", "522.70"],
        ["Total Income (Rs. in Lakhs)", "1762.49", "538.03"],
        ["EBITDA (Rs. in Lakhs)", "469.44", "113.04"],
    ]
    p.grid(72, 100, [260, 90, 90], rows)
    path = tmp_path / "rowunit.pdf"
    path.write_bytes(build_pdf([p]))
    (t,) = parse_pdf(path).pages[0].tables
    assert t.unit is Unit.LAKH
    assert t.unit_text is not None
    assert t.unit_text.startswith("row labels")


# ---- statement rows: column anchors, assembled headers, residual rows, segmentation, workers ----


def _right(p: PageSpec, x1: float, top: float, s: str, size: float = 8) -> None:
    p.text(x1 - 4.45 * len(s), top, s, size)  # Helvetica digits ~0.556 em, comma/period ~0.278


def _two_period_statement() -> PageSpec:
    """Right-aligned statement with a Note column, a header split over three lines, and a row
    that has no value in the first period column."""
    p = PageSpec()
    p.text(72, 60, "(All amounts are in Indian Rupees in Million)", 8)
    p.text(72, 80, "Particulars", 8)
    _right(p, 300, 80, "Note")
    p.text(380, 80, "For the year", 8)
    p.text(480, 80, "For the year", 8)
    p.text(380, 90, "ended March 31,", 8)
    p.text(480, 90, "ended March 31,", 8)
    p.text(400, 100, "2026", 8)
    p.text(500, 100, "2025", 8)
    rows = [
        ("Revenue from operations", "31", "1,000.50", "900.25"),
        ("Other income", "32", "12.75", "9.10"),
        ("Total income", "", "1,013.25", "909.35"),
        ("Exceptional item", "", "", "(5.00)"),  # only the second period has a value
        ("Profit before tax", "", "(50.00)", "40.00"),
    ]
    for i, (label, note, a, b) in enumerate(rows):
        top = 118 + i * 14
        p.text(72, top, label, 8)
        if note:
            _right(p, 300, top, note)
        if a:
            _right(p, 440, top, a)
        _right(p, 540, top, b)
    return p


def _parse_one(tmp_path: Path, spec: PageSpec, name: str = "s.pdf") -> ParsedDocument:
    path = tmp_path / name
    path.write_bytes(build_pdf([spec]))
    return parse_pdf(path)


def test_statement_columns_are_anchored_by_x_position(tmp_path: Path) -> None:
    doc = _parse_one(tmp_path, _two_period_statement())
    (t,) = [t for t in doc.pages[0].tables if t.strategy == "numeric_rows"]
    assert len(t.columns) == 3  # Note + two periods
    assert "2026" in t.columns[1]
    assert "2025" in t.columns[2]
    assert "For the year" in t.columns[1]
    assert t.label_header.startswith("Particulars")
    # the row with a value only in the second period keeps it in the second period column
    row = next(r for r in t.rows if r[0] == "Exceptional item")
    assert row == ["Exceptional item", "", "", "(5.00)"]
    assert next(r for r in t.rows if r[0] == "Total income") == [
        "Total income",
        "",
        "1,013.25",
        "909.35",
    ]
    # header lines are columns, not data rows
    assert not any("ended" in " ".join(r) for r in t.rows)


def test_numeric_lines_outside_a_ruled_table_still_become_rows(tmp_path: Path) -> None:
    p = PageSpec()
    p.grid(72, 60, [200, 100, 100], [["Item", "FY 2024", "FY 2023"], ["Boxed", "1", "2"]])
    for i, (label, a, b) in enumerate(
        [("Loan disbursals", "71,519.55", "50,992.90"), ("Total revenue", "10,411.13", "6,930.46"),
         ("Marketing costs", "1,220.90", "1,073.45"), ("Impairment", "2,614.03", "2,004.30")]
    ):  # fmt: skip
        top = 300 + i * 14
        p.text(72, top, label, 8)
        _right(p, 400, top, a)
        _right(p, 500, top, b)
    doc = _parse_one(tmp_path, p)
    strategies = sorted(t.strategy for t in doc.pages[0].tables)
    assert strategies == ["lines", "numeric_rows"]
    statement = next(t for t in doc.pages[0].tables if t.strategy == "numeric_rows")
    assert ["Total revenue", "10,411.13", "6,930.46"] in statement.rows
    assert not any("Total revenue" in b.text for b in doc.pages[0].blocks)


def test_unrelated_numeric_blocks_are_split_into_separate_tables(tmp_path: Path) -> None:
    p = PageSpec()
    for i in range(3):
        top = 80 + i * 14
        p.text(72, top, f"First block row {i}", 8)
        _right(p, 400, top, f"{100 + i},000.50")
        _right(p, 500, top, f"{200 + i},000.50")
    for j in range(6):  # a paragraph of prose between the two blocks
        p.text(72, 140 + j * 14, "This is ordinary prose that separates the two numeric blocks.", 8)
    for i in range(3):
        top = 300 + i * 14
        p.text(72, top, f"Second block row {i}", 8)
        _right(p, 400, top, f"{300 + i},000.50")
        _right(p, 500, top, f"{400 + i},000.50")
    doc = _parse_one(tmp_path, p)
    tables = [t for t in doc.pages[0].tables if t.strategy == "numeric_rows"]
    assert len(tables) == 2
    assert not any("ordinary prose" in " ".join(r) for t in tables for r in t.rows)


def test_parallel_parse_matches_serial(tmp_path: Path) -> None:
    pages = [_two_period_statement() for _ in range(6)]
    path = tmp_path / "multi.pdf"
    path.write_bytes(build_pdf(pages))
    serial = parse_pdf(path, workers=1)
    parallel = parse_pdf(path, workers=3, min_pages_per_worker=1)

    def strip(d: ParsedDocument) -> list[tuple[int, list[str], list[list[list[str]]]]]:
        return [
            (p.pdf_page, [b.text for b in p.blocks], [t.rows for t in p.tables]) for p in d.pages
        ]

    assert strip(serial) == strip(parallel)
    assert [t.pdf_pages for t in serial.tables] == [t.pdf_pages for t in parallel.tables]


def _word(text: str, x1: float, top: float, width: float = 30.0) -> dict[str, object]:
    return {"text": text, "x0": x1 - width, "x1": x1, "top": top, "bottom": top + 8}


def test_line_with_more_values_than_columns_degrades_to_label_text() -> None:
    from redherring.parse.statements import build_statement_tables

    words: list[dict[str, object]] = []
    for i in range(3):  # three normal rows with two value columns (right edges 400 and 500)
        top = 80 + i * 14
        words += [_word(f"Row{i}", 120, top), _word("100.50", 400, top), _word("200.50", 500, top)]
    # five tightly packed values, all nearest one anchor: cannot be placed one per column
    top = 124
    words += [_word("Crowded", 120, top)] + [
        _word(f"{j}1.00", 396 + j * 2, top, width=2) for j in range(5)
    ]
    (table,) = build_statement_tables(1, words)  # must not raise
    assert ["Row0", "100.50", "200.50"] in table.rows
    crowded = next(r for r in table.rows if r[0].startswith("Crowded"))
    assert len(crowded) == 3  # [label, col1, col2]; width stays consistent
    assert "01.00" in crowded[0]  # the unplaceable values are kept as text, not dropped


def test_page_level_failure_is_recorded_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from redherring.parse import pdf as pdfmod

    real = pdfmod._find_tables

    def flaky(page: object, words: list[dict[str, object]]) -> list[object]:
        if getattr(page, "page_number", 0) == 2:
            raise RuntimeError("boom")
        return real(page, words)  # type: ignore[return-value]

    monkeypatch.setattr(pdfmod, "_find_tables", flaky)
    path = tmp_path / "three.pdf"
    path.write_bytes(build_pdf([PageSpec().text(72, 72, f"Page {i}") for i in (1, 2, 3)]))
    doc = parse_pdf(path)
    assert [p.pdf_page for p in doc.pages] == [1, 2, 3]
    assert doc.pages[1].error is not None
    assert "boom" in doc.pages[1].error
    assert doc.pages[0].error is None
    assert doc.pages[2].blocks  # later pages still parsed
    assert compute_stats(doc).pages_with_errors == 1


def _is_fused_numbers(cell: str) -> bool:
    """Two or more numbers in one cell, e.g. '17,989.49 518.44'."""
    flat = cell.replace(",", "").replace(".", "").replace(" ", "")
    return len(cell.split()) >= 2 and flat.isdigit()


def test_ruled_box_without_row_rules_is_rebuilt_row_by_row(tmp_path: Path) -> None:
    """A ruled header row over one tall body row: pdfplumber returns a single cell per column
    holding every line of the statement (the Runwal p293 shape)."""
    p = PageSpec()
    x_label, x_a, x_b = 72.0, 340.0, 440.0
    widths = (268.0, 100.0, 100.0)
    p.grid(x_label, 100, list(widths), [["Particulars", "FY 2026", "FY 2025"]], row_h=18)
    body_top, body_h = 118.0, 90.0
    for x, w in zip((x_label, x_a, x_b), widths, strict=True):
        p.ops.append(f"{x} {792 - body_top - body_h} {w} {body_h} re S")
    rows = [
        ("Revenue from operations", "17,989.49", "10,077.66"),
        ("Other income", "518.44", "429.48"),
        ("Total income", "18,507.93", "10,507.14"),
        ("Total expenses", "16,268.63", "9,531.54"),
    ]
    for i, (label, a, b) in enumerate(rows):
        y = body_top + 6 + i * 14
        p.text(x_label + 3, y, label, 8)
        _right(p, x_a + 95, y, a)
        _right(p, x_b + 95, y, b)
    doc = _parse_one(tmp_path, p)
    stmts = [t for t in doc.pages[0].tables if t.strategy == "numeric_rows"]
    assert len(stmts) == 1
    assert ["Total income", "18,507.93", "10,507.14"] in stmts[0].rows
    assert ["Revenue from operations", "17,989.49", "10,077.66"] in stmts[0].rows
    assert [t.strategy for t in doc.pages[0].tables] == ["numeric_rows"]  # merged table replaced
    for table in doc.pages[0].tables:
        for r in table.rows:
            assert not any(_is_fused_numbers(c) for c in r)


def test_prose_is_not_turned_into_a_text_table(tmp_path: Path) -> None:
    p = PageSpec()
    lines = [
        "Other expenses increased by 30.15% from Rs. 1,585.70 million for Fiscal 2025 to",
        "Rs. 2,682.75 million for Fiscal 2026, primarily as a result of a decrease in the",
        "amounts allocated to project costs from Rs. 4,027.69 million for Fiscal 2025 to",
        "Rs. 2,227.43 million, and an increase in advertising expenses from Rs. 793.30",
        "million in Fiscal 2025 to Rs. 1,104.60 million in Fiscal 2026 as discussed above.",
        "Total tax expenses decreased by 8.96% from Rs. 419.08 million for Fiscal 2025 to",
    ]
    for i, ln in enumerate(lines):
        p.text(72, 100 + i * 12, ln, 9)
    doc = _parse_one(tmp_path, p)
    assert doc.pages[0].tables == []
    assert any("Other expenses increased" in b.text for b in doc.pages[0].blocks)


def test_header_is_found_above_label_only_rows(tmp_path: Path) -> None:
    """Period header, then section/label lines with no values, then the first data row."""
    p = PageSpec()
    p.text(72, 60, "Annexure II: Restated Consolidated Summary Statement of Profit and Loss", 8)
    p.text(72, 72, "(All amounts are in Indian Rupees in Million)", 8)
    p.text(380, 90, "For the year ended", 8)
    p.text(480, 90, "For the year ended", 8)
    p.text(390, 100, "March 31, 2026", 8)
    p.text(490, 100, "March 31, 2025", 8)
    p.text(72, 116, "Income", 8)
    p.text(72, 128, "Revenue from operations", 8)
    p.text(80, 140, "- Fees and commission income", 8)
    data = [
        ("Fees", "6,328.65", "3,917.61"),
        ("Interest", "3,871.66", "2,829.16"),
        ("Other", "112.83", "102.44"),
    ]
    for i, (label, a, b) in enumerate(data):
        top = 152 + i * 12
        p.text(80, top, f"- {label} income", 8)
        _right(p, 440, top, a)
        _right(p, 540, top, b)
    doc = _parse_one(tmp_path, p)
    (t,) = [t for t in doc.pages[0].tables if t.strategy == "numeric_rows"]
    assert "March 31, 2026" in t.columns[0]
    assert "March 31, 2025" in t.columns[1]
    assert "For the year ended" in t.columns[0]
    assert t.unit is Unit.MILLION
    # label-only lines between the header and the first data row stay in the table as rows
    labels = [r[0] for r in t.rows]
    assert "Income" in labels
    assert "Revenue from operations" in labels


def test_ruled_table_gets_columns_from_leading_header_rows(tmp_path: Path) -> None:
    p = PageSpec()
    rows = [
        ["Particulars", "Fiscal 2026", "Fiscal 2025"],
        ["", "Amount", "Amount"],
        ["", "(Rs. in million)", "(Rs. in million)"],
        ["Revenue from operations", "17,989.49", "10,077.66"],
        ["Other income", "518.44", "429.48"],
    ]
    p.grid(72, 100, [220, 110, 110], rows)
    doc = _parse_one(tmp_path, p)
    (t,) = doc.pages[0].tables
    assert t.n_header_rows == 3
    assert t.columns == [
        "Fiscal 2026 Amount (Rs. in million)",
        "Fiscal 2025 Amount (Rs. in million)",
    ]
    assert t.label_header == "Particulars"
    assert t.unit is Unit.MILLION  # found in the third header row
