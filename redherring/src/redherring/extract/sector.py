"""Which kind of business a filing describes, only as far as the rules need to know.

A lender's operating cash flow is negative while it grows its loan book and a developer's while it
builds inventory, so "cash flow below profit" says nothing about their earnings quality. A rule
can name sectors it does not apply to. Detection counts self-description in the front of the
document; the thresholds were set on nine filings (lenders 61-126 mentions, a payments company 15,
a developer 9 NBFC mentions) and are a measured heuristic, not a classification scheme.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from redherring.parse.models import ParsedDocument

FRONT_PAGES = 150

_SECTORS: dict[str, tuple[re.Pattern[str], int]] = {
    "lender": (
        re.compile(
            r"non[- ]banking financial compan|\bNBFC|housing finance compan|microfinance"
            r"|small finance bank",
            re.I,
        ),
        30,
    ),
    "real_estate": (
        re.compile(r"\bRERA\b|real estate (?:development|projects?)|residential projects?", re.I),
        30,
    ),
}


class SectorEvidence(BaseModel):
    sector: str
    mentions: int
    threshold: int


def detect_sectors(doc: ParsedDocument, *, front_pages: int = FRONT_PAGES) -> list[SectorEvidence]:
    text = [
        " ".join(b.text for b in page.blocks) for page in doc.pages if page.pdf_page <= front_pages
    ]
    out: list[SectorEvidence] = []
    for sector, (pattern, threshold) in _SECTORS.items():
        mentions = sum(len(pattern.findall(t)) for t in text)
        if mentions >= threshold:
            out.append(SectorEvidence(sector=sector, mentions=mentions, threshold=threshold))
    return out
