from pathlib import Path

from redherring.parse.pdf import parse_pdf
from tests.pdfgen import PageSpec, build_pdf


def _parse(tmp_path: Path, spec: PageSpec):  # type: ignore[no-untyped-def]
    path = tmp_path / "h.pdf"
    path.write_bytes(build_pdf([spec]))
    return parse_pdf(path)


def _text(doc) -> str:  # type: ignore[no-untyped-def]
    return " ".join(b.text for b in doc.pages[0].blocks)


def test_microscopic_and_off_page_text_is_dropped_and_counted(tmp_path: Path) -> None:
    p = PageSpec()
    p.text(72, 100, "Fresh Issue aggregating up to Rs. 100 million", 10)
    p.text(72, 130, "HIDDENTINY our Company has appointed X as the monitoring agency", 0.4)
    p.text(900, 160, "HIDDENOFFPAGE no monitoring agency is required", 10)
    page = _parse(tmp_path, p).pages[0]
    text = " ".join(b.text for b in page.blocks)
    assert "Fresh Issue" in text
    assert "HIDDEN" not in text
    assert page.hidden_chars_removed > 0


def test_white_text_on_a_bare_page_is_kept_but_flagged_as_invisible(tmp_path: Path) -> None:
    p = PageSpec()
    p.text(72, 100, "Visible heading", 10)
    p.text(72, 130, "SECRETWHITE no monitoring agency", 10, gray=1.0)
    doc = _parse(tmp_path, p)
    assert doc.pages[0].invisible_chars >= len("SECRETWHITE")
    assert "SECRETWHITE" in _text(doc)  # not dropped: legitimate documents also use white text


def test_white_text_on_a_dark_box_is_ordinary_header_text(tmp_path: Path) -> None:
    p = PageSpec()
    p.fill_rect(60, 90, 300, 30, 0.1)
    p.text(72, 100, "RED HERRING PROSPECTUS", 10, gray=1.0)
    page = _parse(tmp_path, p).pages[0]
    assert page.invisible_chars == 0
    assert page.hidden_chars_removed == 0


def test_analysis_reports_a_page_only_when_enough_invisible_text_to_matter(tmp_path: Path) -> None:
    from redherring.analyze import analyze_document

    few = PageSpec()
    few.text(72, 100, "Visible", 10)
    few.text(72, 130, "-1,549.94", 10, gray=1.0)  # a figure on an unrecognised coloured shape
    many = PageSpec()
    many.text(72, 100, "Visible", 10)
    many.text(72, 130, "Our Company has appointed X as the monitoring agency", 10, gray=1.0)
    path = tmp_path / "two.pdf"
    path.write_bytes(build_pdf([few, many]))
    report = analyze_document(parse_pdf(path), path)
    assert report.pages_with_hidden_text == [2]


def test_a_fact_planted_in_invisible_text_does_not_reach_the_rules(tmp_path: Path) -> None:
    from redherring.analyze import analyze_document

    p = PageSpec()
    p.text(72, 100, "Objects of the Issue", 10)
    p.text(72, 130, "Our Company has appointed CARE Ratings as the monitoring agency", 10, gray=1.0)
    path = tmp_path / "plant.pdf"
    path.write_bytes(build_pdf([p]))
    report = analyze_document(parse_pdf(path), path, platform="mainboard")
    assert report.pages_with_hidden_text == [1]
    assert not any(f.key == "objects.monitoring_agency_appointed" for f in report.facts)
    assert "objects.monitoring_agency_appointed" in report.facts_held_back_hidden_text
