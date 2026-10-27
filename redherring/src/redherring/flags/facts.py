"""Turn extraction results into the cited facts the rules consume."""

from __future__ import annotations

from decimal import Decimal

from redherring.extract.consensus import SIZE_CONCEPTS, Consensus
from redherring.extract.issue import IssueFact
from redherring.flags.engine import Citation, Fact
from redherring.parse.units import MULTIPLIER
from redherring.verify.footing import quantum


def _keep(c: Consensus) -> bool:
    """A figure enters the rules if it is a lone reading or a strong plurality of its sources.

    Strong means at least two independent sources agree and they are at least twice as many as
    the best rival reading. Statements are repeated in several sections, while subsidiary and
    segment tables each add a one-off number, so a repeated figure that clearly leads is the
    entity's own. A close contest means we do not know the figure; a rule must not pick one.
    """
    if c.total == 1:
        return True
    if c.supporters >= 2 and c.strength >= 2 * c.rival_strength:
        return True
    # a size cannot be smaller for the group than for one of its subsidiaries: where the rival is
    # the smaller figure, outweighing it, even by less than two to one, is enough
    return (
        c.concept in SIZE_CONCEPTS
        and c.chosen_is_largest
        and c.supporters >= 2
        and c.strength > c.rival_strength
    )


def facts_from(consensus: list[Consensus], issue_facts: list[IssueFact]) -> dict[str, Fact]:
    facts: dict[str, Fact] = {}
    for c in consensus:
        rupees = c.chosen.rupees
        if rupees is None or not _keep(c):
            continue
        key = f"financials.{c.concept.value}.{c.period_key}"
        facts[key] = Fact(
            key=key,
            value=rupees,
            citations=[Citation(pdf_page=c.chosen.pdf_page, span=c.chosen.span)],
            step=quantum(c.chosen.raw) * MULTIPLIER[c.chosen.unit] if c.chosen.unit else Decimal(1),
        )
    for f in issue_facts:
        facts[f.key.value] = Fact(
            key=f.key.value,
            value=f.value,
            citations=[Citation(pdf_page=f.pdf_page, span=f.span)],
            step=quantum(f.raw) * MULTIPLIER[f.unit] if f.unit else Decimal(1),
        )
    return facts
