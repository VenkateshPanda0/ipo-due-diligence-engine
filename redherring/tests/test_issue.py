from decimal import Decimal

import pytest

from redherring.extract.issue import IssueKey, extract_issue_facts
from redherring.parse.models import BBox, Block, ParsedDocument, ParsedPage, Table
from redherring.parse.units import Unit


def _page(n: int, *texts: str, tables: list[Table] | None = None) -> ParsedPage:
    blocks = [
        Block(pdf_page=n, bbox=BBox(x0=0, top=i * 20.0, x1=500, bottom=i * 20.0 + 10), text=t)
        for i, t in enumerate(texts)
    ]
    return ParsedPage(
        pdf_page=n, width=612, height=792, alnum_chars=500, n_images=0, image_coverage=0.0,
        needs_ocr=False, blocks=blocks,
    )  # fmt: skip


def _doc(*pages: ParsedPage, tables: list[Table] | None = None) -> ParsedDocument:
    return ParsedDocument(doc_id="t", n_pages=len(pages), pages=list(pages), tables=tables or [])


def _facts(doc: ParsedDocument) -> dict[IssueKey, tuple[Decimal, int]]:
    return {f.key: (f.value, f.pdf_page) for f in extract_issue_facts(doc)}


def test_fresh_issue_in_million_from_cover_sentence() -> None:
    doc = _doc(
        _page(
            2,
            "FRESH ISSUE OF 220,588,235* EQUITY SHARES OF FACE VALUE OF ₹ 1 EACH BY OUR COMPANY "
            "AGGREGATING TO ₹ 7,500* MILLION",
        )
    )
    assert _facts(doc)[IssueKey.FRESH_ISSUE_AMOUNT] == (Decimal(7_500_000_000), 2)


def test_fresh_and_ofs_in_one_sentence() -> None:
    doc = _doc(
        _page(
            1,
            "FRESH ISSUE OF UP TO [●] EQUITY SHARES AGGREGATING TO ₹ 83,000 MILLION (THE “FRESH "
            "ISSUE”) AND AN OFFER FOR SALE OF UP TO [●] EQUITY SHARES AGGREGATING UP TO ₹ 40,000 "
            "MILLION",
        )
    )
    facts = _facts(doc)
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT][0] == Decimal(83_000_000_000)
    assert facts[IssueKey.OFS_AMOUNT][0] == Decimal(40_000_000_000)
    assert facts[IssueKey.TOTAL_ISSUE_AMOUNT][0] == Decimal(123_000_000_000)  # fresh + OFS


def test_sme_cover_table_row_in_lakhs() -> None:
    t = Table(
        pdf_pages=[1],
        row_pages=[1],
        rows=[
            ["Type", "Fresh Issue Size", "Offer for Sale", "Total Issue Size"],
            [
                "Fresh Issue",
                "13,40,000 Equity Shares at the Issue Price of Rs. 150.00 each aggregating "
                "Rs 2010.00 Lakhs",
                "N.A.",
                "13,40,000 Equity Shares at the Issue Price of Rs. 150.00 each aggregating "
                "Rs 2010.00 Lakhs",
            ],
        ],
    )
    facts = _facts(_doc(_page(1), tables=[t]))
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT] == (Decimal(201_000_000), 1)
    assert facts[IssueKey.TOTAL_ISSUE_AMOUNT][0] == Decimal(201_000_000)


@pytest.mark.parametrize(
    "text",
    [
        "FRESH ISSUE OF UP TO [●] EQUITY SHARES AGGREGATING UP TO ₹ [●] MILLION",
        "Fresh issue of [●] Equity Shares aggregating up to ₹ [●] million. Separately the "
        "Company reported revenue aggregating ₹ 9,999 million.",
    ],
)
def test_placeholders_produce_no_fact(text: str) -> None:
    assert extract_issue_facts(_doc(_page(1, text))) == []


def test_crore_and_rs_forms() -> None:
    doc = _doc(_page(1, "Fresh Issue of 1,00,000 equity shares aggregating up to Rs. 54.04 crores"))
    assert _facts(doc)[IssueKey.FRESH_ISSUE_AMOUNT][0] == Decimal(540_400_000)


def test_every_fact_carries_page_span_and_raw_text() -> None:
    doc = _doc(_page(7, "Fresh Issue aggregating up to ₹ 5,000.00 million"))
    (f,) = extract_issue_facts(doc)
    assert f.pdf_page == 7
    assert f.raw == "5,000.00"
    assert "5,000.00" in f.span
    assert f.unit is Unit.MILLION


def test_only_early_pages_are_searched() -> None:
    late = _page(60, "Fresh Issue of shares aggregating up to ₹ 1,000 million")
    assert extract_issue_facts(_doc(_page(1, "cover"), late)) == []
    assert len(extract_issue_facts(_doc(late), max_page=80)) == 1


def test_gcp_amount_from_objects_table_and_net_proceeds() -> None:
    t = Table(
        pdf_pages=[140],
        row_pages=[140] * 4,
        unit=Unit.MILLION,
        columns=["Estimated amount"],
        rows=[
            ["1. Investment to drive growth in loan disbursals", "3,250.00"],
            ["2. Investment in WFPL, our Material Subsidiary", "2,500.00"],
            ["3. General corporate purposes(1)", "1,117.15"],
            ["Net Proceeds", "6,867.15"],
        ],
    )
    facts = _facts(_doc(_page(1), tables=[t]))
    assert facts[IssueKey.GCP_AMOUNT] == (Decimal(1_117_150_000), 140)


def test_gcp_placeholder_and_unidentified_acquisition_rows() -> None:
    t = Table(
        pdf_pages=[104],
        row_pages=[104] * 4,
        unit=Unit.MILLION,
        columns=["Estimated amount"],
        rows=[
            ["Repayment of borrowings", "1,000.00"],
            ["Funding acquisitions of future real estate projects", "1,500.00"],
            ["General corporate purposes", "[●]"],
            ["Net Proceeds", "[●]"],
        ],
    )
    facts = _facts(_doc(_page(1), tables=[t]))
    assert IssueKey.GCP_AMOUNT not in facts  # placeholder: unknown, not zero
    assert facts[IssueKey.UNIDENTIFIED_ACQUISITION_AMOUNT][0] == Decimal(1_500_000_000)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Our Company has appointed CARE Ratings as the Monitoring Agency for the Issue.",
            1,
        ),
        (
            "CRISIL Ratings has been appointed as the monitoring agency in terms of Regulation 41.",
            1,
        ),
        ("As the Issue size is below Rs 100 crores, no monitoring agency is required.", 0),
        (
            "The Company is not required to appoint a monitoring agency under the ICDR rules.",
            0,
        ),
    ],
)
def test_monitoring_agency_statement(text: str, expected: int) -> None:
    facts = _facts(_doc(_page(3, text)))
    assert facts[IssueKey.MONITORING_AGENCY_APPOINTED][0] == Decimal(expected)


def test_monitoring_agency_silence_gives_no_fact() -> None:
    assert (
        extract_issue_facts(
            _doc(_page(3, "The Issue is being made through the book building process."))
        )
        == []
    )
