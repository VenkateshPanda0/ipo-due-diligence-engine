"""
Narrative (prose) extraction for non-tabular facts.

Patterns target standard offer-document language. Every narrative result is
EXTRACTED_NEEDS_VERIFICATION: negations and qualifications in legal prose are
easy to misread, so a reviewer must confirm before a rule relies on them.
Suggestions (listing route, issue type, book building) are returned separately;
they never overwrite values a user entered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.intelligence.pages import PageData


@dataclass
class NarrativeFact:
    field_path: str
    value: bool | int | Decimal
    unit: str
    page: int
    snippet: str
    pattern: str


@dataclass
class NarrativeResult:
    facts: list[NarrativeFact] = field(default_factory=list)
    suggestions: dict[str, dict[str, object]] = field(default_factory=dict)
    doc_type: str = "unknown"


def _sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(])", flat) if s.strip()]


_NEGATIVE_DECLARATIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "declarations.debarred_by_sebi",
        re.compile(
            r"(?:company|promoters?|directors?).{0,200}(?:are|is|have) not (?:been )?"
            r"(?:prohibited|debarred)"
            r".{0,120}(?:capital market|securities)",
            re.I,
        ),
    ),
    (
        "declarations.promoter_or_director_of_debarred_company",
        re.compile(
            r"(?:none of|neither).{0,120}(?:promoters?|directors?).{0,160}"
            r"(?:promoters?|directors?) of any "
            r"(?:other )?compan(?:y|ies) which (?:is|are|has been) debarred",
            re.I,
        ),
    ),
    (
        "declarations.wilful_defaulter_or_fraudulent_borrower",
        re.compile(
            r"(?:neither|none of|not been identified as|has not been (?:declared|identified))"
            r".{0,200}wilful defaulters?"
            r"(?:.{0,40}fraudulent borrowers?)?",
            re.I,
        ),
    ),
    (
        "declarations.fugitive_economic_offender",
        re.compile(
            r"(?:none of|neither|not been declared|is not|are not).{0,160}"
            r"fugitive economic offenders?",
            re.I,
        ),
    ),
)


def extract_narrative(pages: list[PageData]) -> NarrativeResult:
    result = NarrativeResult()
    head = " ".join(p.text.lower() for p in pages[:3])
    if "draft red herring prospectus" in head:
        result.doc_type = "drhp"
    elif "red herring prospectus" in head:
        result.doc_type = "rhp"
    elif "prospectus" in head:
        result.doc_type = "prospectus"
    elif "annual report" in head:
        result.doc_type = "annual_report"
    elif "financial statements" in head or "auditor" in head:
        result.doc_type = "financial_statements"

    seen: set[str] = set()
    for page in pages:
        if not page.text:
            continue
        for sentence in _sentences(page.text):
            low = sentence.lower()
            snippet = sentence[:400]
            if (
                "regulation 6(1)" in low
                and "eligib" in low
                and "listing_route" not in result.suggestions
            ):
                result.suggestions["listing_route"] = {
                    "value": "mainboard_reg6_1",
                    "page": page.number,
                    "snippet": snippet,
                }
            if "regulation 6(2)" in low and "eligib" in low:
                result.suggestions["listing_route"] = {
                    "value": "mainboard_reg6_2",
                    "page": page.number,
                    "snippet": snippet,
                }
            if "book building process" in low and "is_book_built" not in result.suggestions:
                result.suggestions["is_book_built"] = {
                    "value": True,
                    "page": page.number,
                    "snippet": snippet,
                }
            if "issue_type" not in result.suggestions:
                has_fresh = re.search(r"\bfresh issue\b", low) is not None
                has_ofs = re.search(r"\boffer for sale\b", low) is not None
                if has_fresh and has_ofs:
                    result.suggestions["issue_type"] = {
                        "value": "mixed",
                        "page": page.number,
                        "snippet": snippet,
                    }
            m = re.search(
                r"not less than 75% of the net offer shall be (?:available for )?allo", low
            )
            if m and "issue_details.qib_net_offer_allocation" not in seen:
                seen.add("issue_details.qib_net_offer_allocation")
                result.facts.append(
                    NarrativeFact(
                        "issue_details.qib_net_offer_allocation",
                        Decimal(75),
                        "PERCENT",
                        page.number,
                        snippet,
                        "qib_75",
                    )
                )
            m = re.search(
                r"locked[- ]in for a period of "
                r"(?:(eighteen|18|thirty[- ]six|36) months?|(three|3) years?)",
                low,
            )
            if m and "promoter.lock_in_months" not in seen and "promoter" in low:
                seen.add("promoter.lock_in_months")
                months = 18 if m.group(1) in ("eighteen", "18") else 36
                result.facts.append(
                    NarrativeFact(
                        "promoter.lock_in_months", months, "MONTHS", page.number, snippet, "lock_in"
                    )
                )
            for path, pattern in _NEGATIVE_DECLARATIONS:
                if path not in seen and pattern.search(sentence):
                    seen.add(path)
                    result.facts.append(
                        NarrativeFact(
                            path,
                            False,
                            "BOOLEAN",
                            page.number,
                            snippet,
                            "standard_negative_declaration",
                        )
                    )
    if "issue_type" not in result.suggestions:
        text = " ".join(p.text.lower() for p in pages[:5])
        fresh = "fresh issue" in text
        ofs = "offer for sale" in text
        if fresh or ofs:
            value = "mixed" if fresh and ofs else ("fresh" if fresh else "offer_for_sale")
            result.suggestions["issue_type"] = {
                "value": value,
                "page": 1,
                "snippet": "cover-page offer description",
            }
    return result
