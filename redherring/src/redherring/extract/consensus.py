"""Agreement between independent occurrences of the same figure.

The same total income appears in the restated statements, the summary financial information, the
KPI table and the management discussion. When independent tables agree, the figure is very likely
read correctly; when they disagree, the disagreement is surfaced, not hidden. Values are compared
in rupees, within the rounding of the coarser printed figure.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from redherring.extract.models import STOCK_CONCEPTS, CitedNumber, Concept
from redherring.extract.periods import fiscal_key
from redherring.parse.units import MULTIPLIER
from redherring.verify.footing import quantum

# Lines that are parts of a total, not rival readings of one figure: never compared.
COMPONENT_CONCEPTS = frozenset({Concept.BORROWINGS})


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

    @property
    def unanimous(self) -> bool:
        return self.supporters == self.total

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
        return (v.table_id, v.concept, fiscal_key(v.period, stock=v.concept in STOCK_CONCEPTS))

    for v in values:
        if (k := key(v)) is not None:
            readings[k].add(v.value)
    kept = [v for v in values if (k := key(v)) is None or len(readings[k]) == 1]
    return kept, len(values) - len(kept)


def build_consensus(
    values: list[CitedNumber], trusted_tables: set[int] | None = None
) -> list[Consensus]:
    """One Consensus per (concept, period) among values with a known unit and period.

    When `trusted_tables` is given and a group has readings from them, only those readings are
    compared (the others are counted in `untrusted_ignored`): a figure from a table whose own
    totals foot is preferred to repeated agreement among tables that cannot be validated.
    """
    groups: dict[tuple[Concept, str], list[CitedNumber]] = defaultdict(list)
    for v in values:
        if (
            v.concept not in COMPONENT_CONCEPTS
            and v.unit is not None
            and v.period is not None
            and v.rupees is not None
        ):
            groups[(v.concept, fiscal_key(v.period, stock=v.concept in STOCK_CONCEPTS))].append(v)

    out: list[Consensus] = []
    for (concept, key), members in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        ignored = 0
        if trusted_tables:
            trusted = [m for m in members if m.table_id in trusted_tables]
            if trusted:
                ignored, members = len(members) - len(trusted), trusted
        clusters: list[list[CitedNumber]] = []
        for v in sorted(members, key=lambda m: m.rupees or Decimal(0)):
            for cluster in clusters:
                ref = cluster[0]
                assert v.rupees is not None and ref.rupees is not None
                if abs(v.rupees - ref.rupees) <= max(_step(v), _step(ref)):
                    cluster.append(v)
                    break
            else:
                clusters.append([v])
        best = max(
            clusters,
            key=lambda c: (len(c), sum(m.confidence for m in c) / len(c)),
        )
        chosen = min(best, key=lambda m: (_step(m), -m.confidence))
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
                untrusted_ignored=ignored,
            )
        )
    return out
