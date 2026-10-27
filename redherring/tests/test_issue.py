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


def test_ofs_amount_is_not_taken_from_the_fresh_issue_column_of_an_interleaved_cover() -> None:
    """Indiqube's cover is a table whose text flattens as heading, fresh-issue cell, OFS cell."""
    doc = _doc(
        _page(
            1,
            "Fresh Issue and an Offer for Sale Fresh issue of up to [●] Equity Shares of face "
            "value ₹1 each aggregating up to ₹6,500.00 million Offer for sale of up to [●] Equity "
            "Shares of face value ₹1 each aggregating up to ₹500.00 million",
        )
    )
    facts = _facts(doc)
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT][0] == Decimal(6_500_000_000)
    assert facts[IssueKey.OFS_AMOUNT][0] == Decimal(500_000_000)


def test_three_column_cover_table_does_not_hand_the_fresh_amount_to_the_offer_for_sale() -> None:
    """Shiprocket: the cover table flattens to 'Fresh Issue and Offer for Sale | up to ... 11,000 |
    up to ... 12,423.53 | up to ... 23,423.53' and the sentence on page 3 states the same three
    figures. The three must be read as fresh + OFS = total, however the layout interleaves them."""
    table = (
        "Fresh Issue and Offer for Sale Up to [●] Equity Shares of face value of ₹ 10 each "
        "aggregating up to ₹ 11,000.00 million Up to [●] Equity Shares of face value of ₹ 10 each "
        "aggregating up to ₹ 12,423.53 million Up to [●] Equity Shares of face value of ₹ 10 each "
        "aggregating up to ₹ 23,423.53 million"
    )
    sentence = (
        "AT A PRICE OF ₹ [●] PER EQUITY SHARE AGGREGATING UP TO ₹ 23,423.53 MILLION COMPRISING A "
        "FRESH ISSUE OF UP TO [●] EQUITY SHARES OF FACE VALUE OF ₹ 10 EACH AGGREGATING UP TO "
        "₹ 11,000.00 MILLION BY OUR COMPANY (“FRESH ISSUE”) AND AN OFFER FOR SALE OF UP TO [●] "
        "EQUITY SHARES OF FACE VALUE OF ₹ 10 EACH AGGREGATING UP TO ₹ 12,423.53 MILLION "
        "(“OFFERED SHARES”) BY THE SELLING SHAREHOLDERS (“OFFER FOR SALE”)"
    )
    facts = _facts(_doc(_page(1, table), _page(3, sentence)))
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT][0] == Decimal(11_000_000_000)
    assert facts[IssueKey.OFS_AMOUNT][0] == Decimal(12_423_530_000)
    assert facts[IssueKey.TOTAL_ISSUE_AMOUNT][0] == Decimal(23_423_530_000)


def test_total_stated_before_comprising_a_fresh_issue_is_the_total() -> None:
    doc = _doc(
        _page(
            2,
            "AGGREGATING UP TO ₹ 7,000.00 MILLION COMPRISING A FRESH ISSUE OF UP TO [●] EQUITY "
            "SHARES AGGREGATING UP TO ₹ 6,500.00 MILLION BY OUR COMPANY",
        )
    )
    facts = _facts(doc)
    assert facts[IssueKey.TOTAL_ISSUE_AMOUNT][0] == Decimal(7_000_000_000)
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT][0] == Decimal(6_500_000_000)


def test_sme_type_row_gives_fresh_and_total_and_nil_offer_for_sale() -> None:
    """Indong Tea: 'Type | Fresh Issue Size | OFS Size | Total Issue Size' then one row."""
    doc = _doc(
        _page(
            1, "Fresh Issue ₹1,301.04 Lakhs Nil ₹1,301.04 Lakhs", "Type Fresh Issue Size OFS Size"
        )
    )
    facts = _facts(doc)
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT][0] == Decimal(130_104_000)
    assert facts[IssueKey.TOTAL_ISSUE_AMOUNT][0] == Decimal(130_104_000)
    assert IssueKey.OFS_AMOUNT not in facts  # "Nil" is not an amount


def test_eligibility_route_is_read_from_the_cover() -> None:
    loss_making = _doc(
        _page(
            1, "The Offer is being made pursuant to Regulation 6(2) of the Securities and Exchange"
        )
    )
    profitable = _doc(
        _page(1, "The Offer is being made pursuant to Regulation 6(1) of the SEBI ICDR Regulations")
    )
    assert _facts(loss_making)[IssueKey.ELIGIBILITY_REG_6_2][0] == 1
    assert _facts(profitable)[IssueKey.ELIGIBILITY_REG_6_2][0] == 0
    assert IssueKey.ELIGIBILITY_REG_6_2 not in _facts(_doc(_page(1, "A cover without the clause")))


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


def test_objects_table_with_a_serial_number_column_and_net_proceeds_only_in_the_header() -> None:
    """SME prospectuses: `Sr. No. | Objects | Amount ... Net Proceeds`, no Net Proceeds row."""
    t = Table(
        pdf_pages=[20, 21],
        row_pages=[20, 20, 21, 21, 21],
        unit=Unit.LAKH,
        columns=["Objects of the Issue", "Amount Proposed to be Utilized from the Net Proceeds"],
        rows=[
            ["1.", "Repayment of certain Borrowings", "500.00"],
            ["3.", "Investment in Strategic Acquisition / Joint Venture", "530.00"],
            ["4.", "General Corporate Purpose", "670.00"],
            ["", "Total", "1700.00"],
        ],
    )
    facts = _facts(_doc(_page(1), tables=[t]))
    assert facts[IssueKey.GCP_AMOUNT] == (Decimal(67_000_000), 21)
    assert facts[IssueKey.UNIDENTIFIED_ACQUISITION_AMOUNT][0] == Decimal(53_000_000)


def test_objects_table_without_any_net_proceeds_wording_is_accepted_only_if_it_foots() -> None:
    def table(total: str) -> Table:
        return Table(
            pdf_pages=[9],
            row_pages=[9] * 4,
            unit=Unit.LAKH,
            columns=["Particular", "Amount"],
            rows=[
                ["1.", "To finance the new showroom", "1550.00"],
                ["2.", "General Corporate Purpose", "400.00"],
                ["", "Total", total],
            ],
        )

    assert IssueKey.GCP_AMOUNT in _facts(_doc(_page(1), tables=[table("1950.00")]))
    assert IssueKey.GCP_AMOUNT not in _facts(_doc(_page(1), tables=[table("9999.00")]))


def test_debt_repayment_amount_from_objects_table_not_from_a_cash_flow_statement() -> None:
    objects = Table(
        pdf_pages=[121],
        row_pages=[121] * 4,
        unit=Unit.MILLION,
        columns=["Amount"],
        rows=[
            ["Repayment / prepayment, in full or in part, of certain borrowings", "3,600.00"],
            ["General corporate purposes", "[●]"],
            ["Net Proceeds", "[●]"],
        ],
    )
    cash_flow = Table(
        pdf_pages=[66],
        row_pages=[66] * 3,
        unit=Unit.MILLION,
        columns=["FY2026"],
        rows=[["Repayment of long-term borrowings", "(1,338.71)"], ["Total", "(1,338.71)"]],
    )
    facts = _facts(_doc(_page(1), tables=[cash_flow, objects]))
    assert facts[IssueKey.DEBT_REPAYMENT_AMOUNT] == (Decimal(3_600_000_000), 121)


def test_debt_repayment_rows_are_summed_unless_a_parent_row_already_totals_them() -> None:
    def table(rows: list[list[str]]) -> Table:
        return Table(
            pdf_pages=[104], row_pages=[104] * len(rows), unit=Unit.MILLION, columns=["Amount"],
            rows=rows,
        )  # fmt: skip

    split = table(
        [
            ["Repayment of borrowings availed by our Company", "400.00"],
            ["Repayment of borrowings availed by our Subsidiaries", "600.00"],
            ["Net Proceeds", "5,000.00"],
        ]
    )
    nested = table(
        [
            ["Repayment of certain borrowings", "1,000.00"],
            ["(i) by our Company", "400.00"],
            ["(ii) by our Subsidiaries", "600.00"],
            ["Net Proceeds", "5,000.00"],
        ]
    )
    for t in (split, nested):
        assert _facts(_doc(_page(1), tables=[t]))[IssueKey.DEBT_REPAYMENT_AMOUNT][0] == Decimal(
            1_000_000_000
        )


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
            "In terms of Regulation 41, our Company has appointed India Ratings and Research "
            "Private Limited to monitor the utilisation of the Gross Proceeds.",
            1,
        ),
        ("Our Company has not appointed any monitoring agency for this Issue.", 0),
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


def test_defined_term_mention_does_not_steal_the_next_amount() -> None:
    """Synoptics-style cover: the offer for sale amount comes after a long list of sellers, and
    the defined term "(Offer for Sale)" is followed by an unrelated market-maker amount."""
    sellers = " and ".join(f"Selling Shareholder Number {i} Private Limited" for i in range(1, 9))
    text = (
        "Public issue of equity shares aggregating to Rs. 5403.60 lakhs (“the offer”), comprising "
        "a fresh issue of up to 14,80,000 equity shares aggregating to Rs. 3507.60 lakhs by our "
        "company (“Fresh Issue”) and an offer for sale of up to 8,00,000 equity shares of face "
        f"value of Rs. 10.00 each by {sellers} (the “Selling Shareholders”) aggregating to "
        "Rs. 1896.00 lakhs (“Offer for Sale”); of the offer, 1,14,000 equity shares aggregating to "
        "Rs. 270.18 lakhs will be reserved for subscription by market maker."
    )
    facts = _facts(_doc(_page(20, text)))
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT][0] == Decimal(350_760_000)
    assert facts[IssueKey.OFS_AMOUNT][0] == Decimal(189_600_000)  # 1896.00 lakhs, not 270.18
    assert facts[IssueKey.TOTAL_ISSUE_AMOUNT][0] == Decimal(540_360_000)


def test_explicit_total_is_preferred_to_the_derived_sum_and_cites_its_own_page() -> None:
    cover = _page(
        3,
        "OF Rs. 34 PER EQUITY SHARE (THE “OFFER PRICE”) AGGREGATING TO Rs. 10,916.80* MILLION "
        "(THE “OFFER”). THE OFFER COMPRISES A FRESH ISSUE OF 220,588,235* EQUITY SHARES BY OUR "
        "COMPANY AGGREGATING TO Rs. 7,500* MILLION (“FRESH ISSUE”) AND AN OFFER FOR SALE OF "
        "100,494,200* EQUITY SHARES AGGREGATING TO Rs. 3,416.80* MILLION (“OFFER FOR SALE”)",
    )
    summary = _page(
        12, "Fresh Issue of 220,588,235* Equity Shares aggregating to Rs. 7,500.00* million"
    )
    facts = {f.key: f for f in extract_issue_facts(_doc(summary, cover))}
    total = facts[IssueKey.TOTAL_ISSUE_AMOUNT]
    assert total.value == Decimal(10_916_800_000)
    assert total.method == "regex"  # stated, not derived
    assert total.pdf_page == 3
    assert total.raw == "10,916.80"
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT].value == Decimal(7_500_000_000)
    assert facts[IssueKey.OFS_AMOUNT].value == Decimal(3_416_800_000)


def test_issue_or_fresh_issue_defined_after_the_amount_is_both_fresh_and_total() -> None:
    """Runwal-style cover: a fresh-issue-only offer, defined as (the “Issue” or “Fresh Issue”)."""
    text = (
        "[●] PER EQUITY SHARE) (THE “ISSUE PRICE”) AGGREGATING UP TO Rs. 5,000.00 MILLION "
        "(THE “ISSUE” OR “FRESH ISSUE”) THE ISSUE INCLUDES A RESERVATION OF UP TO [●] EQUITY "
        "SHARES AGGREGATING UP TO Rs. 35.00 MILLION (CONSTITUTING UP TO [●]% OF THE POST-ISSUE)"
    )
    facts = _facts(_doc(_page(3, text)))
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT] == (Decimal(5_000_000_000), 3)
    assert facts[IssueKey.TOTAL_ISSUE_AMOUNT] == (Decimal(5_000_000_000), 3)
    assert IssueKey.OFS_AMOUNT not in facts


def test_defined_term_roles() -> None:
    fresh_only = _facts(_doc(_page(1, "aggregating to Rs. 7,500 million (“Fresh Issue”)")))
    assert IssueKey.FRESH_ISSUE_AMOUNT in fresh_only
    assert IssueKey.TOTAL_ISSUE_AMOUNT not in fresh_only
    ofs_only = _facts(_doc(_page(1, "aggregating to Rs. 1896.00 lakhs (“Offer for Sale”)")))
    assert ofs_only[IssueKey.OFS_AMOUNT][0] == Decimal(189_600_000)
    assert IssueKey.FRESH_ISSUE_AMOUNT not in ofs_only
    price = _facts(_doc(_page(1, "aggregating to Rs. 34 million (the “Offer Price”)")))
    assert price == {}  # a price is not an issue size


def _cover_table(first: str, fresh: str, ofs: str, total: str, head: list[list[str]]) -> Table:
    row = [
        first,
        f"Up to [●] Equity Shares of face value of ₹2 each aggregating up to {fresh}",
        f"Up to 127,562,573 Equity Shares of face value of ₹2 each aggregating up to {ofs}",
        f"Up to [●] Equity Shares of face value of ₹2 each aggregating up to {total}",
        "This Offer is being made in terms of Regulation 6(2) of the SEBI ICDR Regulations",
    ]
    rows = [*head, row]
    return Table(pdf_pages=[1], row_pages=[1] * len(rows), unit=None, columns=[], rows=rows)


LENSKART_HEAD = [
    ["TYPE", "FRESH ISSUE", "OFFER", "TOTAL OFFER", "ELIGIBILITY"],
    ["", "SIZE", "FOR SALE", "SIZE", ""],
]


def test_cover_table_cells_are_read_by_column_so_a_placeholder_does_not_shift_the_amounts() -> None:
    """Lenskart: fresh ₹21,500.00 million, offer for sale and total still [●]. The text-proximity
    reading took 21,500 for the offer for sale too and derived a total of 43,000."""
    t = _cover_table(
        "Fresh Issue and Offer for Sale",
        "₹21,500.00 million",
        "₹[●] million",
        "₹[●] million",
        LENSKART_HEAD,
    )
    facts = _facts(_doc(_page(1), tables=[t]))
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT][0] == Decimal(21_500_000_000)
    assert IssueKey.OFS_AMOUNT not in facts
    assert IssueKey.TOTAL_ISSUE_AMOUNT not in facts or facts[IssueKey.TOTAL_ISSUE_AMOUNT][
        0
    ] == Decimal(21_500_000_000)


def test_cover_table_with_all_three_amounts_reads_them_by_column() -> None:
    t = _cover_table(
        "Fresh Issue and Offer for Sale",
        "₹700.00 crores",
        "₹400.00 crores",
        "₹1,100.00 crores",
        LENSKART_HEAD,
    )
    facts = _facts(_doc(_page(1), tables=[t]))
    assert facts[IssueKey.FRESH_ISSUE_AMOUNT][0] == Decimal(7_000_000_000)
    assert facts[IssueKey.OFS_AMOUNT][0] == Decimal(4_000_000_000)
    assert facts[IssueKey.TOTAL_ISSUE_AMOUNT][0] == Decimal(11_000_000_000)
