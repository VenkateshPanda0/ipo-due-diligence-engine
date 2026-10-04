"""Table reconstruction on synthetic word layouts modelled on real-DRHP failures.

Each case reproduces a layout seen in the development benchmark documents
(see docs/BENCHMARK_RESULTS.md); none of them uses real company figures.
"""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.candidates import decide, generate
from app.intelligence.layout import Word, build_lines
from app.intelligence.pages import PageData
from app.intelligence.tables import extract_tables, find_period_columns

Row = list[tuple[str, float]]  # (text, x0) pairs on one line


def page(rows: list[Row], number: int = 1, height: float = 800.0) -> PageData:
    words = [
        Word(text, x0, x0 + 5.0 * len(text), 40.0 + 14 * i, 50.0 + 14 * i)
        for i, row in enumerate(rows)
        for text, x0 in row
    ]
    return PageData(
        number, 600.0, height, "native", "native", words=words, lines=build_lines(words)
    )


def candidates(pages: list[PageData]) -> dict[tuple[str, str], object]:
    return {(c.field, c.period_label): c for c in generate(extract_tables(pages))}


def test_split_date_header_cells_are_recovered() -> None:
    # Ekkaa: "March" | "31," | "2025" printed as separate, widely spaced cells.
    rows: list[Row] = [
        [("(₹", 40), ("in", 52), ("lakhs)", 64)],
        [
            ("Particulars", 40),
            ("March", 250),
            ("31,", 300),
            ("2025", 340),
            ("March", 420),
            ("31,", 470),
            ("2024", 510),
        ],
        [("Net", 40), ("worth", 60), ("1,000.00", 320), ("800.00", 490)],
    ]
    cols = find_period_columns(page(rows).lines[1], None)
    assert [c.period.label for c in cols] == ["FY2025", "FY2024"]
    got = candidates([page(rows)])
    assert got[("net_worth", "FY2025")].value == Decimal("10")  # type: ignore[attr-defined]
    assert got[("net_worth", "FY2024")].value == Decimal("8")  # type: ignore[attr-defined]


def test_three_line_header_with_bare_years() -> None:
    # Iris / Jagatjit: "Fiscals" then "Description" then bare years.
    rows: list[Row] = [
        [("(₹", 40), ("in", 52), ("lakhs)", 64)],
        [("Fiscals", 300)],
        [("Description", 40)],
        [("2025", 300), ("2024", 400), ("2023", 500)],
        [("Net", 40), ("worth", 60), ("300", 300), ("200", 400), ("100", 500)],
    ]
    got = candidates([page(rows)])
    assert got[("net_worth", "FY2023")].value == Decimal("1")  # type: ignore[attr-defined]


def test_row_with_more_numbers_than_columns_is_dropped_not_guessed() -> None:
    rows: list[Row] = [
        [("(₹", 40), ("in", 52), ("lakhs)", 64)],
        [("Particulars", 40), ("FY", 300), ("2025", 312), ("FY", 400), ("2024", 412)],
        [("Net", 40), ("worth", 60), ("100", 290), ("150", 340), ("200", 400)],
        [("Net", 40), ("tangible", 60), ("assets", 105), ("90", 300), ("80", 400)],
    ]
    tables = extract_tables([page(rows)])
    assert any("column mismatch" in w for t in tables for w in t.warnings)
    got = candidates([page(rows)])
    assert ("net_worth", "FY2025") not in got and ("net_worth", "FY2024") not in got
    assert got[("net_tangible_assets", "FY2024")].value == Decimal("0.8")  # type: ignore[attr-defined]


def test_per_column_basis_annotation_below_header() -> None:
    rows: list[Row] = [
        [("(₹", 40), ("in", 52), ("lakhs)", 64)],
        [("Particulars", 40), ("FY", 300), ("2025", 312), ("FY", 400), ("2024", 412)],
        [("(Consolidated)", 290), ("(Standalone)", 395)],
        [("Net", 40), ("worth", 60), ("100", 300), ("200", 400)],
    ]
    got = candidates([page(rows)])
    assert got[("net_worth", "FY2025")].basis == "consolidated"  # type: ignore[attr-defined]
    assert got[("net_worth", "FY2024")].basis == "standalone"  # type: ignore[attr-defined]


def test_unit_caption_on_previous_page() -> None:
    first = page(
        [[("Summary", 40), ("of", 90)], [("(₹", 40), ("in", 52), ("lakhs)", 64)]], number=1
    )
    second = page(
        [
            [("Particulars", 40), ("FY", 300), ("2025", 312), ("FY", 400), ("2024", 412)],
            [("Net", 40), ("worth", 60), ("100", 300), ("200", 400)],
        ],
        number=2,
    )
    got = candidates([first, second])
    c = got[("net_worth", "FY2025")]
    assert c.original_unit == "INR_LAKH" and c.value == Decimal("1")  # type: ignore[attr-defined]


def test_unit_from_row_label_when_table_has_none() -> None:
    rows: list[Row] = [
        [("Particulars", 40), ("FY", 300), ("2025", 312), ("FY", 400), ("2024", 412)],
        [
            ("Net", 40),
            ("worth", 60),
            ("(in", 95),
            ("₹", 115),
            ("million)", 125),
            ("50", 300),
            ("40", 400),
        ],
    ]
    c = candidates([page(rows)])[("net_worth", "FY2025")]
    assert c.unit_source == "row_label" and c.value == Decimal("5")  # type: ignore[attr-defined]


def test_no_unit_anywhere_abstains() -> None:
    rows: list[Row] = [
        [("Particulars", 40), ("FY", 300), ("2025", 312), ("FY", 400), ("2024", 412)],
        [("Net", 40), ("worth", 60), ("50", 300), ("40", 400)],
    ]
    c = candidates([page(rows)])[("net_worth", "FY2025")]
    assert c.value is None and c.raw_value == Decimal("50")  # type: ignore[attr-defined]


def test_average_row_is_not_a_yearly_value() -> None:
    rows: list[Row] = [
        [("(₹", 40), ("in", 52), ("lakhs)", 64)],
        [("Particulars", 40), ("FY", 300), ("2025", 312), ("FY", 400), ("2024", 412)],
        [("Average", 40), ("operating", 85), ("profit", 135), ("150", 350)],
        [("Operating", 40), ("profit", 90), ("100", 300), ("200", 400)],
    ]
    got = candidates([page(rows)])
    assert got[("operating_profit", "FY2025")].original_text == "100"  # type: ignore[attr-defined]
    assert all(c.raw_label.lower().find("average") < 0 for c in got.values())  # type: ignore[attr-defined]


def test_mixed_merged_and_split_header_cells() -> None:
    # Ekkaa: "ended March 31, 2026" | "March" | "31," | "2025" | "ended March 31, 2024"
    rows: list[Row] = [
        [("(₹", 40), ("in", 52), ("millions)", 64)],
        [
            ("Particulars", 40),
            ("ended", 200),
            ("March", 230),
            ("31,", 260),
            ("2026", 280),
            ("March", 330),
            ("31,", 370),
            ("2025", 400),
            ("ended", 450),
            ("March", 480),
            ("31,", 510),
            ("2024", 530),
        ],
        [("Net", 40), ("worth", 60), ("30.00", 260), ("20.00", 385), ("10.00", 520)],
    ]
    got = candidates([page(rows)])
    assert [got[("net_worth", y)].original_text for y in ("FY2026", "FY2025", "FY2024")] == [  # type: ignore[attr-defined]
        "30.00",
        "20.00",
        "10.00",
    ]


def test_footnote_prose_below_table_is_not_a_row() -> None:
    rows: list[Row] = [
        [("(₹", 40), ("in", 52), ("lakhs)", 64)],
        [("Particulars", 40), ("FY", 300), ("2025", 312), ("FY", 400), ("2024", 412)],
        [("Net", 40), ("worth", 60), ("100", 300), ("200", 400)],
        [
            ("1.", 40),
            ("Net", 55),
            ("tangible", 75),
            ("assets", 120),
            ("as", 160),
            ("defined", 200),
            ("in", 250),
            ("Section", 270),
            ("2(1)", 310),
            ("of", 340),
            ("the", 360),
            ("Regulations", 400),
        ],
    ]
    got = candidates([page(rows)])
    assert ("net_tangible_assets", "FY2025") not in got


def test_eligibility_table_is_preferred_over_other_tables_with_same_value() -> None:
    other = page(
        [
            [("(₹", 40), ("in", 52), ("lakhs)", 64)],
            [("Particulars", 40), ("FY", 300), ("2025", 312), ("FY", 400), ("2024", 412)],
            [("Net", 40), ("worth", 60), ("100", 300), ("200", 400)],
        ],
        number=1,
    )
    eligibility = page(
        [
            [("Eligibility", 40), ("for", 100), ("the", 120), ("Offer", 140)],
            [("(₹", 40), ("in", 52), ("lakhs)", 64)],
            [("Particulars", 40), ("FY", 300), ("2025", 312), ("FY", 400), ("2024", 412)],
            [("Net", 40), ("worth", 60), ("100", 300), ("200", 400)],
        ],
        number=2,
    )

    cands = [
        c
        for c in generate(extract_tables([other, eligibility]))
        if c.field == "net_worth" and c.period_label == "FY2025"
    ]
    assert decide(cands[0].field_path, cands).selected.page == 2  # type: ignore[union-attr]


def test_bare_rupee_in_row_label_does_not_override_scaled_caption() -> None:
    rows: list[Row] = [
        [("(₹", 40), ("in", 52), ("lakhs)", 64)],
        [("Particulars", 40), ("FY", 300), ("2025", 312), ("FY", 400), ("2024", 412)],
        [("Net", 40), ("worth", 60), ("(₹)", 95), ("100", 300), ("200", 400)],
    ]
    c = candidates([page(rows)])[("net_worth", "FY2025")]
    assert c.original_unit == "INR_LAKH"  # type: ignore[attr-defined]
