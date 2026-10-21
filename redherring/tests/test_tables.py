from redherring.parse.models import BBox, RawTable
from redherring.parse.tables import looks_transposed, stitch_tables, transpose
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
