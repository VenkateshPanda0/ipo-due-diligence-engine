from datetime import date
from decimal import Decimal

from redherring.extract.consensus import Consensus, build_consensus
from redherring.extract.models import CitedNumber, Concept
from redherring.extract.periods import Period, period_key
from redherring.parse.units import Unit
from redherring.verify.cited import check_cited_number, number_on_page
from redherring.verify.footing import run_footing

FY26 = Period(end=date(2026, 3, 31), months=12, instant=False)
FY25 = Period(end=date(2025, 3, 31), months=12, instant=False)
K26 = period_key(FY26)


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


def test_total_income_identity_also_checks_an_income_statement_headed_as_at_31_march() -> None:
    """Synoptics prints its P&L under "As at 31-March-2022": revenue and other income exist only in
    an income statement, so the column is one, whatever its header says."""
    vals = [
        cn(Concept.REVENUE_FROM_OPERATIONS, "5,092.32", period=AT26),
        cn(Concept.OTHER_INCOME, "4.75", period=AT26),
        cn(Concept.TOTAL_INCOME, "5,097.07", period=AT26),
    ]
    (check,) = run_footing(vals)
    assert check.ok


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


# ---- trusted tables: figures from tables whose own identities hold win over agreeing noise -------


def test_trusted_columns_outweigh_agreeing_untrusted_noise() -> None:
    noise = [cn(Concept.PROFIT_AFTER_TAX, "(0.06)", table_id=t) for t in (10, 11, 12, 13, 14)]
    real = [cn(Concept.PROFIT_AFTER_TAX, "556.48", table_id=t) for t in (1, 2)]
    (plain,) = build_consensus([*noise, *real])
    assert plain.chosen.raw == "(0.06)"  # without trust, the larger noise cluster wins
    (trusted,) = build_consensus([*noise, *real], trusted={(1, K26), (2, K26)})
    assert trusted.chosen.raw == "556.48"
    assert trusted.supporters == 2
    assert trusted.total == 2
    assert trusted.untrusted_ignored == 5


def test_a_column_that_foots_beats_agreeing_untrusted_columns_in_the_same_table_family() -> None:
    """Runwal: PBT before associate share (2,239.30) printed in three cash-flow tables outvotes the
    P&L's 2,239.15 unless trust is per column; the P&L's other year fails (sign convention)."""
    real = cn(Concept.PROFIT_BEFORE_TAX, "2,239.15", table_id=58)
    echoes = [cn(Concept.PROFIT_BEFORE_TAX, "2,239.30", table_id=t) for t in (59, 249, 277)]
    (c,) = build_consensus([real, *echoes], trusted={(58, K26)})
    assert c.chosen.raw == "2,239.15"
    assert c.untrusted_ignored == 3


def test_within_a_cluster_the_figure_most_tables_print_exactly_is_chosen() -> None:
    """Varyaa: 538.03 in the statements and 538.02 in one MD&A table agree to a printed step; the
    reported figure must be the statements', whichever table happened to come first."""
    vals = [
        cn(Concept.TOTAL_INCOME, "538.02", table_id=1),
        cn(Concept.TOTAL_INCOME, "538.03", table_id=2),
        cn(Concept.TOTAL_INCOME, "538.03", table_id=3),
    ]
    (c,) = build_consensus(vals)
    assert c.chosen.raw == "538.03"
    assert c.supporters == 3


def test_cash_flow_profit_is_a_starting_line_and_loses_to_the_income_statement() -> None:
    """Runwal FY2024: three cash-flow statements start from 'profit before tax' 1,567.73 (before the
    share of associates) and outnumber the income statement's 1,567.71; the cash-flow figure is a
    reconciliation line, not the reported one."""
    pnl = [cn(Concept.PROFIT_BEFORE_TAX, "1,567.71", table_id=t) for t in (1, 2)]
    cash = []
    for t in (10, 11, 12):
        cash += [
            cn(Concept.PROFIT_BEFORE_TAX, "1,567.73", table_id=t),
            cn(Concept.CASH_FROM_OPERATIONS, "-549.48", table_id=t),
        ]
    consensus = {c.concept: c for c in build_consensus([*pnl, *cash])}
    pbt = consensus[Concept.PROFIT_BEFORE_TAX]
    assert pbt.chosen.raw == "1,567.71"
    assert pbt.supporters == 2 and pbt.total == 2
    # with no income statement at all, the cash-flow reading is better than nothing
    only_cash = [v for v in cash if v.concept is Concept.PROFIT_BEFORE_TAX]
    both = {c.concept: c for c in build_consensus([*only_cash, *cash[1::2]])}
    assert both[Concept.PROFIT_BEFORE_TAX].chosen.raw == "1,567.73"


def test_without_any_trusted_value_all_sources_still_count() -> None:
    vals = [cn(Concept.TOTAL_INCOME, "100.00", table_id=t) for t in (1, 2, 3)]
    (c,) = build_consensus(vals, trusted={(99, K26)})
    assert c.chosen.raw == "100.00"
    assert c.total == 3
    assert c.untrusted_ignored == 0


def test_trusted_columns_are_those_that_foot_and_never_fail() -> None:
    from redherring.verify.footing import trusted_columns

    ok = [
        cn(Concept.REVENUE_FROM_OPERATIONS, "100.00", table_id=1),
        cn(Concept.OTHER_INCOME, "10.00", table_id=1),
        cn(Concept.TOTAL_INCOME, "110.00", table_id=1),
    ]
    bad = [
        cn(Concept.REVENUE_FROM_OPERATIONS, "100.00", table_id=2),
        cn(Concept.OTHER_INCOME, "10.00", table_id=2),
        cn(Concept.TOTAL_INCOME, "999.00", table_id=2),
    ]
    mixed = [  # foots in one period, fails in another: only the footing column is trusted
        cn(Concept.REVENUE_FROM_OPERATIONS, "100.00", table_id=3, period=FY26),
        cn(Concept.OTHER_INCOME, "10.00", table_id=3, period=FY26),
        cn(Concept.TOTAL_INCOME, "110.00", table_id=3, period=FY26),
        cn(Concept.REVENUE_FROM_OPERATIONS, "90.00", table_id=3, period=FY25),
        cn(Concept.OTHER_INCOME, "9.00", table_id=3, period=FY25),
        cn(Concept.TOTAL_INCOME, "1.00", table_id=3, period=FY25),
    ]
    assert trusted_columns(run_footing([*ok, *bad, *mixed])) == {(1, K26), (3, K26)}


def test_figures_printed_in_the_front_of_the_document_outweigh_a_subsidiary_appendix() -> None:
    """Lenskart: the group's total income 70,092.76 is in the offer summary and the financial
    information; two subsidiary statements near the end each foot on their own and tied it 2-2."""
    main = [
        cn(Concept.TOTAL_INCOME, "70,092.76", table_id=1, page=35),
        cn(Concept.TOTAL_INCOME, "70,092.76", table_id=2, page=124),
        cn(Concept.TOTAL_INCOME, "70,092.76", table_id=3, page=412),
    ]
    subs = [
        cn(Concept.TOTAL_INCOME, "2,726.38", table_id=4, page=800),
        cn(Concept.TOTAL_INCOME, "2,726.38", table_id=5, page=826),
    ]
    (c,) = build_consensus([*main, *subs], n_pages=1000)
    assert c.chosen.raw == "70,092.76"
    assert c.strength == 5 and c.rival_strength == 2
    assert _kept(c)


def _kept(c: Consensus) -> bool:
    from redherring.flags.facts import _keep

    return _keep(c)


def test_untrusted_readings_that_agree_with_a_trusted_figure_corroborate_it() -> None:
    """Lenskart: the offer-summary table has no other-income line, so it cannot foot and is not
    trusted, but it prints the same 70,092.76 as the two statements that do foot."""
    trusted_main = [
        cn(Concept.TOTAL_INCOME, "70,092.76", table_id=2, page=124),
        cn(Concept.TOTAL_INCOME, "70,092.76", table_id=3, page=412),
    ]
    summary = cn(Concept.TOTAL_INCOME, "70,092.76", table_id=1, page=35)  # not trusted, agrees
    noise = cn(Concept.TOTAL_INCOME, "9,999.00", table_id=9, page=90)  # not trusted, disagrees
    sub = [cn(Concept.TOTAL_INCOME, "2,726.38", table_id=t, page=800 + t) for t in (4, 5)]
    trusted = {(t, K26) for t in (2, 3, 4, 5)}
    (c,) = build_consensus([*trusted_main, summary, noise, *sub], trusted=trusted, n_pages=1000)
    assert c.chosen.raw == "70,092.76"
    assert c.supporters == 3  # the trusted two plus the agreeing summary
    assert c.untrusted_ignored == 1  # only the disagreeing reading is set aside
    assert _kept(c)


def test_a_reading_under_a_qualified_entity_header_does_not_count_for_the_group() -> None:
    """Tata Capital prints 'TCL (excluding TMFL)' columns with their own total income beside the
    consolidated ones; the qualified reading is another entity's figure."""
    group = [cn(Concept.TOTAL_INCOME, "283,698.7", table_id=t, page=20 + t) for t in (1, 2)]
    qualified = []
    for t in (3, 4, 5):
        v = cn(Concept.TOTAL_INCOME, "235,673.1", table_id=t, page=300 + t)
        qualified.append(v.model_copy(update={"column_header": "TCL (excluding TMFL) Fiscal 2025"}))
    (c,) = build_consensus([*group, *qualified], n_pages=800)
    assert c.chosen.raw == "283,698.7"
    assert _kept(c)


def test_for_size_concepts_the_larger_supported_figure_breaks_a_near_tie_with_a_subsidiary() -> (
    None
):
    """Lenskart total assets: the group's 104,710 (front page weight 2, plus one more) against a
    subsidiary's 1,099.6 printed twice; a subsidiary cannot be larger than its group."""
    main = [
        cn(Concept.TOTAL_ASSETS, "104,710.19", table_id=1, page=122),
        cn(Concept.TOTAL_ASSETS, "104,710.19", table_id=2, page=700),
    ]
    sub = [cn(Concept.TOTAL_ASSETS, "1,099.60", table_id=t, page=800 + t) for t in (3, 4)]
    (c,) = build_consensus([*main, *sub], n_pages=1000)
    assert c.chosen.raw == "104,710.19"
    assert _kept(c)
    # profit is not a size: a subsidiary may out-earn its group, so a 3-2 split is still withheld
    prof = [cn(Concept.PROFIT_AFTER_TAX, "100.00", table_id=t, page=700 + t) for t in (1, 2)]
    prof_sub = [cn(Concept.PROFIT_AFTER_TAX, "900.00", table_id=t, page=800 + t) for t in (3, 4)]
    (p,) = build_consensus([*prof, *prof_sub], n_pages=1000)
    assert not _kept(p)
