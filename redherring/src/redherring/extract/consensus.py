"""Agreement between independent occurrences of the same figure.

The same total income appears in the restated statements, the summary financial information, the
KPI table and the management discussion. When independent tables agree, the figure is very likely
read correctly; when they disagree, the disagreement is surfaced, not hidden. Values are compared
in rupees, within the rounding of the coarser printed figure.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from redherring.extract.models import CitedNumber, Concept
from redherring.extract.periods import fiscal_key, period_key
from redherring.parse.units import MULTIPLIER
from redherring.verify.footing import quantum

# Lines that are parts of a total, not rival readings of one figure: never compared.
COMPONENT_CONCEPTS = frozenset({Concept.BORROWINGS})

# In a cash-flow statement "profit before tax" is the line the reconciliation starts from, often
# before the share of associates or exceptional items: a rival reading, not a confirmation, of the
# income statement's figure.
_RECONCILIATION_START = frozenset(
    {Concept.PROFIT_BEFORE_TAX, Concept.PROFIT_AFTER_TAX, Concept.TAX_EXPENSE}
)


@dataclass(frozen=True)
class Consensus:
    concept: Concept
    period_key: str
    chosen: CitedNumber
    supporters: int  # values agreeing with `chosen`
    total: int  # all comparable values for this concept and period
    alternatives: list[CitedNumber]  # values that disagree with `chosen`
    cluster_sizes: list[int]  # sizes of all agreement clusters, largest first
    untrusted_ignored: int = 0  # readings set aside because trusted tables had the figure
    weights: list[int] = field(default_factory=list)  # cluster weights, largest first (see below)
    chosen_is_largest: bool = False  # `chosen` is the largest-valued of the agreement clusters

    @property
    def unanimous(self) -> bool:
        return self.supporters == self.total

    @property
    def strength(self) -> int:
        """Weight behind `chosen` (page-position weighted; the plain count if unweighted)."""
        return self.weights[0] if self.weights else self.supporters

    @property
    def rival_strength(self) -> int:
        return (self.weights[1] if len(self.weights) > 1 else 0) if self.weights else self.runner_up

    @property
    def runner_up(self) -> int:
        """Support of the best rival reading (0 if there is none)."""
        return self.cluster_sizes[1] if len(self.cluster_sizes) > 1 else 0


def _step(v: CitedNumber) -> Decimal:
    assert v.unit is not None
    return quantum(v.raw) * MULTIPLIER[v.unit]


def drop_ambiguous(values: list[CitedNumber]) -> tuple[list[CitedNumber], int]:
    """Remove values where one table gives several different readings of the same figure.

    A balance sheet has "trade receivables" in more than one section; a table that lists a
    concept twice for one period with different numbers does not tell us which is "the" figure.
    Equal readings (the same number repeated) are not ambiguous. Returns (kept, number dropped).
    """
    readings: dict[tuple[int, Concept, str], set[Decimal]] = defaultdict(set)

    def key(v: CitedNumber) -> tuple[int, Concept, str] | None:
        if v.period is None:
            return None
        return (v.table_id, v.concept, fiscal_key(v.period))

    for v in values:
        if (k := key(v)) is not None:
            readings[k].add(v.value)
    kept = [v for v in values if (k := key(v)) is None or len(readings[k]) == 1]
    return kept, len(values) - len(kept)


def _column(v: CitedNumber) -> tuple[int, str] | None:
    return (v.table_id, period_key(v.period)) if v.period is not None else None


FRONT_FRACTION = 0.25  # the offer summary and key financials sit in the first quarter
FRONT_WEIGHT = 2


# A column headed with an entity qualifier shows another entity's figure beside the group's.
_OTHER_ENTITY = re.compile(
    r"excluding|\bex[- ]|\bexcl\b|standalone|stand-alone|subsidiar|segment|pro[- ]?forma", re.I
)

# Concepts that measure size: a subsidiary's cannot exceed its group's.
SIZE_CONCEPTS = frozenset(
    {
        Concept.REVENUE_FROM_OPERATIONS,
        Concept.TOTAL_INCOME,
        Concept.TOTAL_EXPENSES,
        Concept.TOTAL_ASSETS,
        Concept.TOTAL_EQUITY_AND_LIABILITIES,
    }
)


def _weight(v: CitedNumber, n_pages: int | None) -> int:
    """A figure printed in the front of the document counts double.

    The issuer's own consolidated figures are in the offer summary and the summary financial
    information; subsidiary statements, which also foot, are appended near the end. Where `n_pages`
    is given, front-of-document readings weigh more when a tie has to be broken.
    """
    if n_pages and _OTHER_ENTITY.search(v.column_header):
        return 0
    return FRONT_WEIGHT if n_pages and v.pdf_page <= FRONT_FRACTION * n_pages else 1


def _agrees(a: CitedNumber, b: CitedNumber) -> bool:
    assert a.rupees is not None and b.rupees is not None
    return abs(a.rupees - b.rupees) <= max(_step(a), _step(b))


def _cluster(members: list[CitedNumber]) -> list[list[CitedNumber]]:
    clusters: list[list[CitedNumber]] = []
    for v in sorted(members, key=lambda m: m.rupees or Decimal(0)):
        for cluster in clusters:
            if _agrees(v, cluster[0]):
                cluster.append(v)
                break
        else:
            clusters.append([v])
    return clusters


def build_consensus(
    values: list[CitedNumber],
    trusted: set[tuple[int, str]] | None = None,
    n_pages: int | None = None,
) -> list[Consensus]:
    """One Consensus per (concept, period) among values with a known unit and period.

    When `trusted` (table, period) columns are given and a group has readings from them, only
    those readings are compared (the others are counted in `untrusted_ignored`): a figure from a
    column whose own totals foot is preferred to repeated agreement among columns that cannot be
    validated.
    """
    cash_flow_tables = {v.table_id for v in values if v.concept is Concept.CASH_FROM_OPERATIONS}
    groups: dict[tuple[Concept, str], list[CitedNumber]] = defaultdict(list)
    for v in values:
        if (
            v.concept not in COMPONENT_CONCEPTS
            and v.unit is not None
            and v.period is not None
            and v.rupees is not None
        ):
            groups[(v.concept, fiscal_key(v.period))].append(v)

    out: list[Consensus] = []
    for (concept, key), members in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        ignored = 0
        if concept in _RECONCILIATION_START:
            statements = [m for m in members if m.table_id not in cash_flow_tables]
            if statements:
                ignored, members = len(members) - len(statements), statements
        untrusted: list[CitedNumber] = []
        if trusted:
            kept = [m for m in members if _column(m) in trusted]
            if kept:
                untrusted = [m for m in members if _column(m) not in trusted]
                members = kept
        clusters = _cluster(members)
        # a reading from a column that cannot be checked still corroborates a trusted figure it
        # agrees with; one that disagrees is set aside
        for m in untrusted:
            home = next((c for c in clusters if _agrees(m, c[0])), None)
            if home is not None:
                home.append(m)
            else:
                ignored += 1
        members = [m for c in clusters for m in c]

        def score(c: list[CitedNumber]) -> int:
            return sum(_weight(m, n_pages) for m in c)

        best = max(clusters, key=lambda c: (score(c), sum(m.confidence for m in c) / len(c)))
        # inside a cluster the readings may differ by a printed step (538.02 vs 538.03): report the
        # one most tables print exactly, then the finest, then the most confident.
        exact = Counter(m.value for m in best)
        chosen = min(best, key=lambda m: (-exact[m.value], _step(m), -m.confidence))
        others = [m for c in clusters if c is not best for m in c]
        out.append(
            Consensus(
                concept=concept,
                period_key=key,
                chosen=chosen,
                supporters=len(best),
                total=len(members),
                alternatives=others,
                cluster_sizes=sorted((len(c) for c in clusters), reverse=True),
                weights=sorted((score(c) for c in clusters), reverse=True) if n_pages else [],
                chosen_is_largest=all(
                    (best[0].rupees or Decimal(0)) >= (c[0].rupees or Decimal(0)) for c in clusters
                ),
                untrusted_ignored=ignored,
            )
        )
    return out
