from redherring.parse.models import BBox, RawTable
from redherring.parse.tables import inherit_headers, looks_transposed, stitch_tables, transpose
from redherring.parse.units import Unit

HEIGHTS = {1: 792.0, 2: 792.0, 3: 792.0}


def _raw(
    page: int, top: float, bottom: float, rows: list[list[str]], unit: Unit | None = None
) -> RawTable:
    return RawTable(
        pdf_page=page,
        bbox=BBox(x0=50, top=top, x1=500, bottom=bottom),
        rows=rows,
        strategy="lines",
        unit=unit,
        unit_text="in lakhs" if unit else None,
    )


HEADER = ["Particulars", "March 31, 2024", "March 31, 2023"]


def test_stitch_multi_page_with_repeated_header() -> None:
    p1 = _raw(1, 600, 760, [HEADER, ["Revenue", "100", "90"]], Unit.LAKH)
    p2 = _raw(2, 60, 200, [HEADER, ["Expenses", "70", "60"]])
    (t,) = stitch_tables([p1, p2], HEIGHTS)
    assert t.pdf_pages == [1, 2]
    assert t.stitched_from == 2
    assert t.rows == [HEADER, ["Revenue", "100", "90"], ["Expenses", "70", "60"]]
    assert t.unit is Unit.LAKH


def test_no_stitch_when_not_at_page_edges() -> None:
    p1 = _raw(1, 100, 300, [HEADER, ["Revenue", "100", "90"]])
    p2 = _raw(2, 60, 200, [HEADER, ["Expenses", "70", "60"]])
    assert len(stitch_tables([p1, p2], HEIGHTS)) == 2


def test_no_stitch_when_column_count_differs() -> None:
    p1 = _raw(1, 600, 760, [HEADER, ["Revenue", "100", "90"]])
    p2 = _raw(2, 60, 200, [["a", "b"], ["c", "d"]])
    assert len(stitch_tables([p1, p2], HEIGHTS)) == 2


def test_no_stitch_when_units_differ() -> None:
    p1 = _raw(1, 600, 760, [HEADER, ["Revenue", "100", "90"]], Unit.LAKH)
    p2 = _raw(2, 60, 200, [HEADER, ["Revenue", "1", "1"]], Unit.CRORE)
    assert len(stitch_tables([p1, p2], HEIGHTS)) == 2


def test_transposed_table_is_flagged_but_not_flipped() -> None:
    rows = [
        ["Period", "Revenue", "PAT"],
        ["March 31, 2024", "100", "10"],
        ["March 31, 2023", "90", "8"],
        ["March 31, 2022", "70", "5"],
    ]
    assert looks_transposed(rows)
    (t,) = stitch_tables([_raw(1, 100, 300, rows)], HEIGHTS)
    assert t.transposed_suspect
    assert t.rows == rows  # as found
    assert transpose(t.rows)[0] == ["Period", "March 31, 2024", "March 31, 2023", "March 31, 2022"]


def test_normal_table_not_transposed() -> None:
    rows = [HEADER, ["Revenue", "100", "90"], ["PAT", "10", "8"]]
    assert not looks_transposed(rows)


def test_transpose_pads_ragged_rows() -> None:
    assert transpose([["a", "b"], ["c"]]) == [["a", "c"], ["b", ""]]


def test_stitched_table_remembers_the_page_of_every_row() -> None:
    p1 = _raw(1, 600, 760, [HEADER, ["Revenue", "100", "90"], ["COGS", "40", "35"]], Unit.LAKH)
    p2 = _raw(2, 60, 200, [HEADER, ["Expenses", "70", "60"], ["PAT", "30", "25"]])
    (t,) = stitch_tables([p1, p2], HEIGHTS)
    assert [r[0] for r in t.rows] == ["Particulars", "Revenue", "COGS", "Expenses", "PAT"]
    # repeated header on page 2 was dropped together with its page entry
    assert t.row_pages == [1, 1, 1, 2, 2]
    assert len(t.row_pages) == len(t.rows)


def test_single_page_table_row_pages_default_to_its_page() -> None:
    (t,) = stitch_tables([_raw(3, 100, 300, [HEADER, ["Revenue", "100", "90"]])], HEIGHTS)
    assert t.row_pages == [3, 3]


# ---- header inheritance for continuation statements --------------------------------------------


def _stmt(
    page: int, top: float, columns: list[str], anchors: list[float], unit: Unit | None = None
) -> RawTable:
    return RawTable(
        pdf_page=page,
        bbox=BBox(x0=50, top=top, x1=500, bottom=top + 100),
        rows=[["Total income", *["1.00"] * len(anchors)]],
        strategy="numeric_rows",
        columns=columns,
        anchors=anchors,
        unit=unit,
    )


def test_headerless_statement_inherits_header_from_matching_table_above() -> None:
    head = _stmt(1, 100, ["FY 2026", "FY 2025"], [300.0, 400.0], Unit.MILLION)
    tail = _stmt(2, 80, ["", ""], [301.5, 399.0])
    inherit_headers([head, tail])
    assert tail.columns == ["FY 2026", "FY 2025"]
    assert tail.unit is Unit.MILLION
    assert tail.header_inherited_from == 1
    assert head.header_inherited_from is None


def test_inheritance_requires_matching_column_layout_and_proximity() -> None:
    head = _stmt(1, 100, ["FY 2026", "FY 2025"], [300.0, 400.0])
    other_layout = _stmt(2, 80, ["", ""], [300.0, 450.0])
    far = _stmt(5, 80, ["", ""], [300.0, 400.0])
    own_header = _stmt(2, 300, ["FY 2024", "FY 2023"], [300.0, 400.0])
    inherit_headers([head, other_layout, far, own_header])
    assert other_layout.columns == ["", ""]
    assert far.columns == ["", ""]  # more than two pages away
    assert own_header.columns == ["FY 2024", "FY 2023"]  # keeps its own header


# ---- a new statement is not a continuation ------------------------------------------------------


def _ruled(
    page: int, top: float, bottom: float, rows: list[list[str]], columns: list[str], n_header: int
) -> RawTable:
    return RawTable(
        pdf_page=page,
        bbox=BBox(x0=50, top=top, x1=500, bottom=bottom),
        rows=rows,
        strategy="lines",
        columns=columns,
        n_header_rows=n_header,
    )


def test_a_table_with_its_own_different_header_starts_a_new_table() -> None:
    """Balance sheet at the foot of page 1, income statement at the top of page 2."""
    bs = _ruled(
        1, 600, 760,
        [["Particulars", "As at March 31, 2026"], ["Total assets", "100"]],
        ["As at March 31, 2026"], 1,
    )  # fmt: skip
    pnl = _ruled(
        2, 60, 200,
        [["Particulars", "For the year ended March 31, 2026"], ["Revenue", "80"]],
        ["For the year ended March 31, 2026"], 1,
    )  # fmt: skip
    tables = stitch_tables([bs, pnl], HEIGHTS)
    assert len(tables) == 2
    assert tables[1].columns == ["For the year ended March 31, 2026"]


def test_the_same_header_repeated_is_still_a_continuation() -> None:
    head = ["For the year ended March 31, 2026"]
    p1 = _ruled(1, 600, 760, [["Particulars", head[0]], ["Revenue", "80"]], head, 1)
    p2 = _ruled(2, 60, 200, [["Particulars", head[0]], ["Expenses", "50"]], head, 1)
    (t,) = stitch_tables([p1, p2], HEIGHTS)
    assert t.stitched_from == 2
    assert [r[0] for r in t.rows] == ["Particulars", "Revenue", "Expenses"]


def test_headerless_continuation_is_still_stitched() -> None:
    p1 = _ruled(1, 600, 760, [["Particulars", "FY 2026"], ["Revenue", "80"]], ["FY 2026"], 1)
    p2 = _ruled(2, 60, 200, [["Expenses", "50"], ["PAT", "30"]], [], 0)
    (t,) = stitch_tables([p1, p2], HEIGHTS)
    assert t.stitched_from == 2
    assert t.columns == ["FY 2026"]
