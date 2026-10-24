from datetime import date
from decimal import Decimal

from redherring.extract.consensus import build_consensus
from redherring.extract.models import CitedNumber, Concept
from redherring.extract.periods import Period
from redherring.parse.units import Unit
from redherring.verify.cited import check_cited_number, number_on_page
from redherring.verify.footing import run_footing

FY26 = Period(end=date(2026, 3, 31), months=12, instant=False)
FY25 = Period(end=date(2025, 3, 31), months=12, instant=False)


def cn(
    concept: Concept,
    raw: str,
    *,
    period: Period | None = FY26,
    unit: Unit | None = Unit.MILLION,
    table_id: int = 0,
    page: int = 5,
    span: str | None = None,
    confidence: float = 0.9,
) -> CitedNumber:
    value = Decimal(raw.replace(",", "").replace("(", "-").replace(")", ""))
    return CitedNumber(
        concept=concept,
        label=concept.value,
        raw=raw,
        value=value,
        unit=unit,
        period=period,
        column_header="h",
        pdf_page=page,
        table_pages=[page],
        table_id=table_id,
        span=span if span is not None else f"{concept.value} | {raw}",
        confidence=confidence,
    )


# ---- cited-value checks ----------------------------------------------------------------------


def test_number_on_page_ignores_whitespace_splits() -> None:
    assert number_on_page("9,521.29", "Cash 9 ,521.29 4,871.75")
    assert number_on_page("(1,234.50)", "Profit (1,234.50) for the year")
    assert not number_on_page("9,521.29", "Cash 9,521.30")


def test_check_cited_number_passes_when_everything_lines_up() -> None:
    v = cn(Concept.TOTAL_INCOME, "1,013.25")
    res = check_cited_number(v, lambda page: "Total income 1,013.25 909.35" if page == 5 else "")
    assert res.ok
    assert res.reasons == []


def test_check_cited_number_fails_when_page_text_lacks_the_number() -> None:
    v = cn(Concept.TOTAL_INCOME, "1,013.25")
    res = check_cited_number(v, lambda page: "completely different page")
    assert not res.ok
    assert "not found on cited page" in res.reasons[0]


def test_check_cited_number_fails_when_span_lacks_the_number_or_page_not_in_table() -> None:
    bad_span = cn(Concept.TOTAL_INCOME, "1,013.25", span="Total income | 999.00")
    assert not check_cited_number(bad_span, lambda p: "1,013.25").ok
    off_page = cn(Concept.TOTAL_INCOME, "1,013.25").model_copy(update={"pdf_page": 9})
    res = check_cited_number(off_page, lambda p: "1,013.25")
    assert not res.ok
    assert any("table pages" in r for r in res.reasons)


# ---- footing -----------------------------------------------------------------------------------


def test_total_income_foots() -> None:
    vals = [
        cn(Concept.REVENUE_FROM_OPERATIONS, "1,000.50"),
        cn(Concept.OTHER_INCOME, "12.75"),
        cn(Concept.TOTAL_INCOME, "1,013.25"),
    ]
    (check,) = run_footing(vals)
    assert check.ok
    assert check.name == "total_income = revenue_from_operations + other_income"
    assert check.expected == Decimal("1013.25")


def test_footing_tolerates_rounding_but_not_real_differences() -> None:
    rounding = [
        cn(Concept.REVENUE_FROM_OPERATIONS, "17,989.49"),
        cn(Concept.OTHER_INCOME, "518.44"),
        cn(Concept.TOTAL_INCOME, "18,507.94"),  # 0.01 off: rounding in the printed figures
    ]
    assert run_footing(rounding)[0].ok
    wrong = [
        cn(Concept.REVENUE_FROM_OPERATIONS, "17,989.49"),
        cn(Concept.OTHER_INCOME, "518.44"),
        cn(Concept.TOTAL_INCOME, "18,600.00"),
    ]
    assert not run_footing(wrong)[0].ok


def test_pat_foots_with_signs() -> None:
    vals = [
        cn(Concept.PROFIT_BEFORE_TAX, "(50.00)"),
        cn(Concept.TAX_EXPENSE, "5.00"),
        cn(Concept.PROFIT_AFTER_TAX, "(55.00)"),
    ]
    assert run_footing(vals)[0].ok


def test_footing_groups_by_table_and_period() -> None:
    vals = [
        cn(Concept.REVENUE_FROM_OPERATIONS, "100.00", period=FY26),
        cn(Concept.OTHER_INCOME, "10.00", period=FY26),
        cn(Concept.TOTAL_INCOME, "110.00", period=FY26),
        cn(Concept.REVENUE_FROM_OPERATIONS, "90.00", period=FY25),
        cn(Concept.OTHER_INCOME, "9.00", period=FY25),
        cn(Concept.TOTAL_INCOME, "50.00", period=FY25),  # wrong in FY25 only
        cn(Concept.TOTAL_INCOME, "999.00", table_id=1),  # other table: nothing to foot against
    ]
    checks = run_footing(vals)
    assert sorted((c.period_key, c.ok) for c in checks) == [("FY2025", False), ("FY2026", True)]


def test_footing_skips_ambiguous_groups() -> None:
    vals = [
        cn(Concept.REVENUE_FROM_OPERATIONS, "100.00"),
        cn(Concept.REVENUE_FROM_OPERATIONS, "101.00"),  # two candidate rows: ambiguous
        cn(Concept.OTHER_INCOME, "10.00"),
        cn(Concept.TOTAL_INCOME, "110.00"),
    ]
    assert run_footing(vals) == []


# ---- consensus ---------------------------------------------------------------------------------


def test_consensus_picks_the_value_most_tables_agree_on() -> None:
    vals = [
        cn(Concept.TOTAL_INCOME, "18,507.93", table_id=0),
        cn(Concept.TOTAL_INCOME, "18,507.93", table_id=1),
        cn(Concept.TOTAL_INCOME, "18,508", table_id=2),  # rounded to a coarser unit step
        cn(Concept.TOTAL_INCOME, "17,000.00", table_id=3),  # outlier
    ]
    (c,) = build_consensus(vals)
    assert c.chosen.raw in {"18,507.93", "18,508"}
    assert (c.supporters, c.total) == (3, 4)
    assert len(c.alternatives) == 1
    assert c.alternatives[0].raw == "17,000.00"
    assert not c.unanimous


def test_consensus_converts_units_before_comparing() -> None:
    vals = [
        cn(Concept.TOTAL_INCOME, "1,850.79", unit=Unit.CRORE, table_id=0),
        cn(Concept.TOTAL_INCOME, "18,507.9", unit=Unit.MILLION, table_id=1),
    ]
    (c,) = build_consensus(vals)
    assert c.unanimous
    assert c.supporters == 2


def test_consensus_ignores_values_without_unit_or_period() -> None:
    vals = [
        cn(Concept.TOTAL_INCOME, "100.00", unit=None),
        cn(Concept.TOTAL_INCOME, "100.00", period=None),
    ]
    assert build_consensus(vals) == []


AT26 = Period(end=date(2026, 3, 31), months=None, instant=True)


def test_flow_identities_are_not_applied_to_balance_sheet_columns() -> None:
    """'Profit for the year' inside a balance sheet is an equity line, not the P&L result."""
    vals = [
        cn(Concept.PROFIT_BEFORE_TAX, "2,239.30", period=AT26),
        cn(Concept.TAX_EXPENSE, "40.00", period=AT26),
        cn(Concept.PROFIT_AFTER_TAX, "937.00", period=AT26),
    ]
    assert run_footing(vals) == []


def test_balance_identity_needs_a_balance_sheet_column() -> None:
    vals = [
        cn(Concept.TOTAL_ASSETS, "500.00", period=AT26),
        cn(Concept.TOTAL_EQUITY_AND_LIABILITIES, "500.00", period=AT26),
    ]
    (check,) = run_footing(vals)
    assert check.ok
    flow = [
        cn(Concept.TOTAL_ASSETS, "500.00", period=FY26),
        cn(Concept.TOTAL_EQUITY_AND_LIABILITIES, "500.00", period=FY26),
    ]
    assert run_footing(flow) == []  # a 12-month flow column is not a balance sheet


def test_component_concepts_are_not_compared_for_consensus() -> None:
    """Non-current and current borrowings are parts of a total, not rival values for it."""
    vals = [
        cn(Concept.BORROWINGS, "4,223.75", table_id=0),
        cn(Concept.BORROWINGS, "12,865.43", table_id=0),
    ]
    assert build_consensus(vals) == []


# ---- generic evidence check (issue facts) ----------------------------------------------------


def test_check_evidence_for_text_facts() -> None:
    from redherring.verify.cited import check_evidence

    ok = check_evidence(
        "1,117.15", "3. General corporate purposes | 1,117.15", 140, lambda p: "1,117.15"
    )
    assert ok.ok
    missing = check_evidence(
        "1,117.15", "General corporate purposes | 1,117.15", 140, lambda p: "other"
    )
    assert not missing.ok
    assert "not found on cited page 140" in missing.reasons[0]
    not_in_span = check_evidence(
        "9.99", "General corporate purposes | 1,117.15", 140, lambda p: "9.99"
    )
    assert not not_in_span.ok
    assert "not in cited span" in not_in_span.reasons[0]


# ---- fiscal keys for balance-sheet (stock) concepts ---------------------------------------------


def test_stock_concepts_at_31_march_share_the_fiscal_year_key() -> None:
    """A 31 March balance and a 'FY2026' KPI figure are the same fact and must be compared."""
    vals = [
        cn(Concept.NET_WORTH, "10,536.08", period=AT26, table_id=0),
        cn(Concept.NET_WORTH, "10,536.08", period=FY26, table_id=1),
    ]
    (c,) = build_consensus(vals)
    assert c.period_key == "FY2026"
    assert c.unanimous
    assert c.total == 2


def test_flow_concepts_keep_their_own_keys() -> None:
    vals = [cn(Concept.TOTAL_INCOME, "100.00", period=FY26)]
    (c,) = build_consensus(vals)
    assert c.period_key == "FY2026"
    june = Period(end=date(2026, 6, 30), months=None, instant=True)
    (s,) = build_consensus([cn(Concept.TRADE_RECEIVABLES, "5.00", period=june)])
    assert s.period_key == "AT-2026-06-30"  # not a fiscal year end: unchanged


# ---- selection policy: plurality and in-table ambiguity -----------------------------------------


def test_consensus_records_cluster_sizes_and_runner_up() -> None:
    vals = [
        cn(Concept.TOTAL_INCOME, "100.00", table_id=0),
        cn(Concept.TOTAL_INCOME, "100.00", table_id=1),
        cn(Concept.TOTAL_INCOME, "100.00", table_id=2),
        cn(Concept.TOTAL_INCOME, "100.00", table_id=3),
        cn(Concept.TOTAL_INCOME, "55.00", table_id=4),
        cn(Concept.TOTAL_INCOME, "55.00", table_id=5),
        cn(Concept.TOTAL_INCOME, "7.00", table_id=6),
    ]
    (c,) = build_consensus(vals)
    assert c.cluster_sizes == [4, 2, 1]
    assert c.runner_up == 2
    assert c.supporters == 4


def test_values_ambiguous_within_one_table_are_dropped() -> None:
    from redherring.extract.consensus import drop_ambiguous

    # one table, one concept and period, two different readings (e.g. current and non-current)
    twice = [
        cn(Concept.TRADE_RECEIVABLES, "1.35", table_id=3, span="a | 1.35"),
        cn(Concept.TRADE_RECEIVABLES, "950.20", table_id=3, span="b | 950.20"),
    ]
    other = cn(Concept.TRADE_RECEIVABLES, "950.20", table_id=4)
    same_value_twice = [
        cn(Concept.TOTAL_INCOME, "10.00", table_id=5, span="x | 10.00"),
        cn(Concept.TOTAL_INCOME, "10.00", table_id=5, span="y | 10.00"),
    ]
    kept, dropped = drop_ambiguous([*twice, other, *same_value_twice])
    assert dropped == 2
    assert {v.table_id for v in kept if v.concept is Concept.TRADE_RECEIVABLES} == {4}
    assert len([v for v in kept if v.concept is Concept.TOTAL_INCOME]) == 2  # equal readings agree
