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

from redherring.extract.models import CitedNumber, Concept
from redherring.extract.periods import period_key
from redherring.parse.units import MULTIPLIER
from redherring.verify.footing import quantum


@dataclass(frozen=True)
class Consensus:
    concept: Concept
    period_key: str
    chosen: CitedNumber
    supporters: int  # values agreeing with `chosen`
    total: int  # all comparable values for this concept and period
    alternatives: list[CitedNumber]  # values that disagree with `chosen`

    @property
    def unanimous(self) -> bool:
        return self.supporters == self.total


def _step(v: CitedNumber) -> Decimal:
    assert v.unit is not None
    return quantum(v.raw) * MULTIPLIER[v.unit]


def build_consensus(values: list[CitedNumber]) -> list[Consensus]:
    """One Consensus per (concept, period) among values with a known unit and period."""
    groups: dict[tuple[Concept, str], list[CitedNumber]] = defaultdict(list)
    for v in values:
        if v.unit is not None and v.period is not None and v.rupees is not None:
            groups[(v.concept, period_key(v.period))].append(v)

    out: list[Consensus] = []
    for (concept, key), members in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
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
            )
        )
    return out
