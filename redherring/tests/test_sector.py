from pathlib import Path

from redherring.extract.sector import detect_sectors
from redherring.flags.engine import audit, evaluate
from redherring.flags.spec import load_rule_file
from redherring.parse.models import BBox, Block, ParsedDocument, ParsedPage


def _doc(*texts_by_page: str) -> ParsedDocument:
    pages = []
    for n, text in enumerate(texts_by_page, 1):
        block = Block(pdf_page=n, bbox=BBox(x0=0, top=0, x1=500, bottom=10), text=text)
        pages.append(
            ParsedPage(
                pdf_page=n, width=612, height=792, alnum_chars=500, n_images=0,
                image_coverage=0.0, needs_ocr=False, blocks=[block],
            )
        )  # fmt: skip
    return ParsedDocument(doc_id="t", n_pages=len(pages), pages=pages, tables=[])


def test_a_lender_is_recognised_by_how_often_it_calls_itself_one() -> None:
    nbfc = "We are a Non-Banking Financial Company registered with the RBI. " * 40
    assert "lender" in {s.sector for s in detect_sectors(_doc(nbfc))}
    # a payments company mentions NBFCs a handful of times without being one
    mention = "Our partners include NBFC lenders. " * 10
    assert detect_sectors(_doc(mention)) == []


def test_real_estate_developer_is_recognised_by_rera_and_project_language() -> None:
    text = "Our residential projects are registered under RERA. " * 20
    assert {s.sector for s in detect_sectors(_doc(text))} == {"real_estate"}


def test_only_the_front_of_the_document_is_read() -> None:
    late = _doc(*(["filler"] * 200), "Non-Banking Financial Company " * 100)
    assert detect_sectors(late) == []


CFO_RULE = Path(__file__).parent.parent / "src/redherring/flags/rules/fin_cfo_vs_pat.toml"


def test_cash_flow_rule_is_not_applied_to_lenders_or_developers() -> None:
    rule = load_rule_file(CFO_RULE)
    assert {"lender", "real_estate"} <= set(rule.not_for_sectors)
    (a,) = audit([rule], {}, platform="mainboard", sectors={"lender"})
    assert a.status == "not_applicable"
    assert "lender" in a.detail
    (b,) = audit([rule], {}, platform="mainboard", sectors=set())
    assert b.status == "missing_inputs"
    assert evaluate([rule], {}, platform="mainboard", sectors={"real_estate"}) == []
