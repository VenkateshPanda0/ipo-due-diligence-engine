"""Accounting identities as label-free correctness checks.

If total income does not equal revenue plus other income in the same table and period, one of the
three numbers was read wrong (or the table is not what we think it is). Passing proves nothing
alone, but across many tables it is a measurable signal that needs no hand labels.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from redherring.extract.models import CitedNumber, Concept
from redherring.extract.periods import Period, period_key

# (name, kind, target, [(sign, part), ...]): the target should equal the signed sum of the parts.
# kind "flow" applies to period columns (income statement), "stock" to "as at" columns (balance
# sheet): "profit for the year" inside a balance sheet is an equity line, not the P&L result.
_IDENTITIES: tuple[tuple[str, str, Concept, tuple[tuple[int, Concept], ...]], ...] = (
    (
        "total_income = revenue_from_operations + other_income",
        "flow",
        Concept.TOTAL_INCOME,
        ((1, Concept.REVENUE_FROM_OPERATIONS), (1, Concept.OTHER_INCOME)),
    ),
    (
        "profit_after_tax = profit_before_tax - tax_expense",
        "flow",
        Concept.PROFIT_AFTER_TAX,
        ((1, Concept.PROFIT_BEFORE_TAX), (-1, Concept.TAX_EXPENSE)),
    ),
    (
        "total_assets = total_equity_and_liabilities",
        "stock",
        Concept.TOTAL_ASSETS,
        ((1, Concept.TOTAL_EQUITY_AND_LIABILITIES),),
    ),
)


def _applies(kind: str, period: Period | None) -> bool:
    if period is None:
        return True  # unknown column: cannot rule it out
    if kind == "stock":
        return period.instant or period.months is None
    return not period.instant


@dataclass(frozen=True)
class FootingCheck:
    name: str
    table_id: int
    period_key: str
    expected: Decimal  # the target as printed
    actual: Decimal  # signed sum of the parts as printed
    tolerance: Decimal
    ok: bool


def quantum(raw: str) -> Decimal:
    """Smallest printed step of `raw`: 0.01 for '1,234.50', 1 for '1,234'."""
    m = re.search(r"\.(\d+)", raw)
    return Decimal(1).scaleb(-len(m.group(1))) if m else Decimal(1)


def run_footing(values: list[CitedNumber]) -> list[FootingCheck]:
    """Evaluate each identity once per (table, period) where every needed value is unambiguous."""
    groups: dict[tuple[int, str], dict[Concept, list[CitedNumber]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for v in values:
        key = period_key(v.period) if v.period else f"col:{v.column_header}"
        groups[(v.table_id, key)][v.concept].append(v)

    checks: list[FootingCheck] = []
    for (table_id, key), by_concept in sorted(groups.items()):
        for name, kind, target, parts in _IDENTITIES:
            needed = [target, *(p for _, p in parts)]
            if any(len(by_concept.get(c, [])) != 1 for c in needed):
                continue  # missing or ambiguous: do not guess
            t = by_concept[target][0]
            if not _applies(kind, t.period):
                continue
            units = {t.unit, *(by_concept[p][0].unit for _, p in parts)}
            if len(units) != 1:
                continue  # mixed units inside one table cell group: not comparable as printed
            actual = sum((s * by_concept[p][0].value for s, p in parts), Decimal(0))
            tol = max(quantum(by_concept[c][0].raw) for c in needed) * (len(parts) + 1)
            checks.append(
                FootingCheck(
                    name=name,
                    table_id=table_id,
                    period_key=key,
                    expected=t.value,
                    actual=actual,
                    tolerance=tol,
                    ok=abs(t.value - actual) <= tol,
                )
            )
    return checks


def trusted_tables(checks: list[FootingCheck]) -> set[int]:
    """Tables with at least one passing identity and no failing one.

    A table whose totals foot is evidently a genuine statement read correctly; subsidiary and
    segment tables, which cannot be validated this way, should not outvote it by repetition.
    """
    passed = {c.table_id for c in checks if c.ok}
    failed = {c.table_id for c in checks if not c.ok}
    return passed - failed
