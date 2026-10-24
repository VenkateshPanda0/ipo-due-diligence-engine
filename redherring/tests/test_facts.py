from datetime import date
from decimal import Decimal

from redherring.extract.consensus import build_consensus
from redherring.extract.issue import IssueFact, IssueKey
from redherring.extract.models import CitedNumber, Concept
from redherring.extract.periods import Period
from redherring.flags.facts import facts_from
from redherring.parse.units import Unit

FY26 = Period(end=date(2026, 3, 31), months=12, instant=False)
FY25 = Period(end=date(2025, 3, 31), months=12, instant=False)


def cn(concept: Concept, raw: str, period: Period, table_id: int = 0, page: int = 9) -> CitedNumber:
    return CitedNumber(
        concept=concept, label=concept.value, raw=raw, value=Decimal(raw.replace(",", "")),
        unit=Unit.MILLION, period=period, column_header="h", pdf_page=page, table_pages=[page],
        table_id=table_id, span=f"{concept.value} | {raw}", confidence=0.9,
    )  # fmt: skip


def test_financial_consensus_becomes_period_keyed_facts_in_rupees() -> None:
    values = [
        cn(Concept.REVENUE_FROM_OPERATIONS, "1,000.00", FY26),
        cn(Concept.REVENUE_FROM_OPERATIONS, "900.00", FY25),
        cn(Concept.CASH_FROM_OPERATIONS, "50.00", FY26),
    ]
    facts = facts_from(build_consensus(values), [])
    rev = facts["financials.revenue_from_operations.FY2026"]
    assert rev.value == Decimal(1_000_000_000)  # rupees, whatever the table's unit
    assert rev.citations[0].pdf_page == 9
    assert "1,000.00" in rev.citations[0].span
    assert "financials.revenue_from_operations.FY2025" in facts
    assert "financials.cash_from_operations.FY2026" in facts


def test_disputed_figures_are_left_out_rather_than_guessed() -> None:
    values = [
        cn(Concept.TOTAL_INCOME, "100.00", FY26, table_id=0),
        cn(Concept.TOTAL_INCOME, "250.00", FY26, table_id=1),  # two tables, two answers
    ]
    assert facts_from(build_consensus(values), []) == {}


def test_agreeing_sources_are_kept_and_a_lone_value_is_kept() -> None:
    values = [
        cn(Concept.TOTAL_INCOME, "100.00", FY26, table_id=0),
        cn(Concept.TOTAL_INCOME, "100", FY26, table_id=1),
        cn(Concept.PROFIT_AFTER_TAX, "7.00", FY26, table_id=2),
    ]
    facts = facts_from(build_consensus(values), [])
    assert "financials.total_income.FY2026" in facts
    assert "financials.profit_after_tax.FY2026" in facts


def test_issue_facts_use_their_enum_key() -> None:
    f = IssueFact(
        key=IssueKey.GCP_AMOUNT, value=Decimal(240_000_000), raw="240.00", unit=Unit.MILLION,
        pdf_page=88, span="General corporate purposes | 240.00", method="table_row",
        confidence=0.85,
    )  # fmt: skip
    facts = facts_from([], [f])
    assert facts["objects.gcp_amount"].value == Decimal(240_000_000)
    assert facts["objects.gcp_amount"].citations[0].pdf_page == 88
