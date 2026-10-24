"""Issue and objects facts the red-flag rules need, from cover text and objects tables.

Deterministic patterns only. A placeholder such as "[●]" (common in draft documents) yields no
fact, never zero; a missing statement yields no fact, never "no". Every fact keeps its page and
the text it came from, and `verify` can re-check it against the PDF.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from redherring.extract.financials import normalise_label
from redherring.parse.models import ParsedDocument, Table
from redherring.parse.units import MULTIPLIER, Unit, detect_unit, parse_amount

DEFAULT_COVER_PAGES = 40


class IssueKey(StrEnum):
    FRESH_ISSUE_AMOUNT = "issue.fresh_issue_amount"
    OFS_AMOUNT = "issue.ofs_amount"
    TOTAL_ISSUE_AMOUNT = "issue.total_issue_amount"
    GCP_AMOUNT = "objects.gcp_amount"
    UNIDENTIFIED_ACQUISITION_AMOUNT = "objects.unidentified_acquisition_amount"
    MONITORING_AGENCY_APPOINTED = "objects.monitoring_agency_appointed"


class IssueFact(BaseModel):
    key: IssueKey
    value: Decimal = Field(description="Rupees for amounts; 1 or 0 for yes/no facts")
    raw: str = Field(description="The figure or phrase exactly as printed")
    unit: Unit | None = None
    pdf_page: int
    span: str = Field(description="Text the fact was read from")
    method: str
    confidence: float = Field(ge=0.0, le=1.0)


_AMT = r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*\**\s*(million|mn|lakhs?|lacs?|crores?|cr)\b"
# Up to 1200 characters, never crossing a sentence end (". " + capital) or another "aggregating":
# the first "aggregating" after the phrase belongs to it. A mention that is itself a quoted
# defined term, as in (“Offer for Sale”), is skipped: the amount precedes it, not follows it.
_GAP = r"(?:(?!\.\s+[A-Z])(?!aggregat).){0,1200}?"
_NOT_DEFINED = r"(?<![“\"(])"
_FRESH = re.compile(
    rf"{_NOT_DEFINED}fresh\s+issue\b{_GAP}aggregat\w*\s*(?:to\s+|up\s+to\s+)?{_AMT}", re.I
)
_OFS = re.compile(
    rf"{_NOT_DEFINED}offer\s+for\s+sale\b{_GAP}aggregat\w*\s*(?:to\s+|up\s+to\s+)?{_AMT}", re.I
)
# "... aggregating to Rs. 5,000.00 million (the "Issue" or "Fresh Issue")": the amount comes first
# and the defined term after it says what the amount is. `_roles` reads that term; "Offer Price"
# and other terms are not roles.
_DEFINED_AFTER = re.compile(
    rf"aggregat\w*\s*(?:to\s+|up\s+to\s+)?{_AMT}\s*\(([^)]{{1,80}})\)", re.I
)


def _roles(term: str) -> set[IssueKey]:
    words = re.sub(r"[“”\"'*]", "", term).lower().split()
    if words[:1] == ["the"]:
        words = words[1:]
    roles: set[IssueKey] = set()
    if words in (["offer"], ["issue"]) or (words[:1] in (["offer"], ["issue"]) and "or" in words):
        roles.add(IssueKey.TOTAL_ISSUE_AMOUNT)
    if "fresh issue" in " ".join(words):
        roles.add(IssueKey.FRESH_ISSUE_AMOUNT)
    if " ".join(words) == "offer for sale":
        roles.add(IssueKey.OFS_AMOUNT)
    return roles


_NOT_APPLICABLE = re.compile(r"\bN\.?\s?A\.?\b|\bnil\b", re.I)

_UNIT_WORDS = {
    "million": Unit.MILLION,
    "mn": Unit.MILLION,
    "lakh": Unit.LAKH,
    "lakhs": Unit.LAKH,
    "lac": Unit.LAKH,
    "lacs": Unit.LAKH,
    "crore": Unit.CRORE,
    "crores": Unit.CRORE,
    "cr": Unit.CRORE,
}

_APPOINTED = re.compile(
    r"(?:has|have)\s+appointed\s+(?:(?!\.\s+[A-Z]).){0,120}?\bmonitoring\s+agency\b"
    r"|\bappointed\s+(?:(?!\.\s+[A-Z]).){0,60}?as\s+(?:the\s+)?monitoring\s+agency\b"
    r"|\bmonitoring\s+agency\b(?:(?!\.\s+[A-Z]).){0,80}?(?:has|have)\s+been\s+appointed",
    re.I,
)
_NOT_REQUIRED = re.compile(
    r"\bno\s+monitoring\s+agency\b"
    r"|\bmonitoring\s+agency\b(?:(?!\.\s+[A-Z]).){0,100}?\b(?:is|are|shall\s+be|will\s+be)\s+not\s+"
    r"(?:required|applicable|necessary)"
    r"|\bnot\s+required\s+to\s+(?:appoint|have|engage)\s+(?:a\s+)?monitoring\s+agency\b",
    re.I,
)


def _num(text: str) -> Decimal | None:
    return parse_amount(text)


def _amount(match: re.Match[str]) -> tuple[Decimal, str, Unit] | None:
    raw = match.group(1)
    value = _num(raw)
    unit = _UNIT_WORDS.get(match.group(2).lower())
    if value is None or unit is None:
        return None
    return value * MULTIPLIER[unit], raw, unit


def _segments(doc: ParsedDocument, max_page: int) -> list[tuple[int, str]]:
    """(page, text) pieces of the early pages: each prose block and each table row."""
    out: list[tuple[int, str]] = []
    for page in doc.pages:
        if page.pdf_page > max_page:
            continue
        out += [(page.pdf_page, " ".join(b.text.split())) for b in page.blocks]
    for t in doc.tables:
        for i, row in enumerate(t.rows):
            pg = t.row_pages[i] if i < len(t.row_pages) else t.pdf_pages[0]
            if pg <= max_page:
                out.append((pg, " ".join(" ".join(c for c in row if c).split())))
    return out


def _cover_amounts(doc: ParsedDocument, max_page: int) -> list[IssueFact]:
    found: dict[IssueKey, IssueFact] = {}
    row_na: dict[int, bool] = {}
    for page, text in _segments(doc, max_page):
        for dm in _DEFINED_AFTER.finditer(text):
            amount = _amount(dm)
            if not amount:
                continue
            value, raw, unit = amount
            for role in _roles(dm.group(3)):
                found.setdefault(
                    role,
                    IssueFact(
                        key=role,
                        value=value,
                        raw=raw,
                        unit=unit,
                        pdf_page=page,
                        span=text[max(0, dm.start() - 40) : dm.end() + 20],
                        method="regex",
                        confidence=0.85,
                    ),
                )
    for page, text in _segments(doc, max_page):
        for key, pattern in ((IssueKey.FRESH_ISSUE_AMOUNT, _FRESH), (IssueKey.OFS_AMOUNT, _OFS)):
            if key in found:
                continue
            m = pattern.search(text)
            amount = _amount(m) if m else None
            if m and amount:
                value, raw, unit = amount
                found[key] = IssueFact(
                    key=key,
                    value=value,
                    raw=raw,
                    unit=unit,
                    pdf_page=page,
                    span=text[max(0, m.start() - 40) : m.end() + 20],
                    method="regex",
                    confidence=0.8,
                )
                row_na[page] = bool(_NOT_APPLICABLE.search(text[m.end() :]))
    fresh, ofs = found.get(IssueKey.FRESH_ISSUE_AMOUNT), found.get(IssueKey.OFS_AMOUNT)
    facts = list(found.values())
    if IssueKey.TOTAL_ISSUE_AMOUNT in found:
        pass  # the total is stated outright; never derive over it
    elif fresh and ofs:
        facts.append(_total(fresh, ofs.value, f"{fresh.span} + {ofs.span}"))
    elif fresh and not ofs and row_na.get(fresh.pdf_page):
        facts.append(_total(fresh, Decimal(0), f"{fresh.span} (no offer for sale: N.A.)"))
    return facts


def _total(fresh: IssueFact, extra: Decimal, span: str) -> IssueFact:
    return IssueFact(
        key=IssueKey.TOTAL_ISSUE_AMOUNT,
        value=fresh.value + extra,
        raw=fresh.raw,
        unit=fresh.unit,
        pdf_page=fresh.pdf_page,
        span=span,
        method="derived",
        confidence=0.7,
    )


_GCP_LABEL = re.compile(r"general corporate purposes?(?:\(\d+\))?")


def _is_unidentified_acquisition(label: str) -> bool:
    has_acq = "acquisition" in label or "inorganic" in label
    return has_acq and any(w in label for w in ("future", "unidentified", "inorganic", "strategic"))


def _split_row(row: list[str]) -> tuple[str, list[str]] | None:
    """(label, cells after it): the label is the first cell with words, past any serial number."""
    for i, cell in enumerate(row):
        if sum(c.isalpha() for c in cell) >= 3:
            return normalise_label(cell), row[i + 1 :]
    return None


def _first_amount(cells: list[str]) -> tuple[Decimal, str] | None:
    for cell in cells:
        value = parse_amount(cell)
        if value is not None:
            return value, cell
    return None


def _foots(rows: list[tuple[str, list[str]]]) -> bool:
    """Do the amounts above a "Total" row add up to it? True for a genuine objects table."""
    amounts: list[Decimal] = []
    for label, cells in rows:
        amount = _first_amount(cells)
        if amount is None:
            continue
        if label.startswith("total"):
            return bool(amounts) and abs(sum(amounts, Decimal(0)) - amount[0]) <= Decimal("0.02")
        amounts.append(amount[0])
    return False


def _is_objects_table(t: Table, rows: list[tuple[str, list[str]]]) -> bool:
    """An objects table states its amounts in a unit and is about the Net Proceeds: it totals them,
    names them in a header, or has rows that foot to a Total."""
    if t.unit is None:
        return False
    if any("net proceeds" in label for label, _ in rows) or any(
        "net proceeds" in c.lower() for c in t.columns
    ):
        return True
    return _foots(rows)


def _objects_from_tables(doc: ParsedDocument) -> list[IssueFact]:
    found: dict[IssueKey, IssueFact] = {}
    for t in doc.tables:
        unit = t.unit
        split = [(i, sp) for i, row in enumerate(t.rows) if row and (sp := _split_row(row))]
        if unit is None or not _is_objects_table(t, [sp for _, sp in split]):
            continue
        for i, (label, cells) in split:
            if _GCP_LABEL.fullmatch(label) or label.startswith("general corporate purpose"):
                key = IssueKey.GCP_AMOUNT
            elif _is_unidentified_acquisition(label):
                key = IssueKey.UNIDENTIFIED_ACQUISITION_AMOUNT
            else:
                continue
            amount = _first_amount(cells)
            if amount is None or key in found:
                continue  # placeholder or repeated table: keep the first stated amount
            value, raw = amount
            found[key] = IssueFact(
                key=key,
                value=value * MULTIPLIER[unit],
                raw=raw,
                unit=unit,
                pdf_page=t.row_pages[i] if i < len(t.row_pages) else t.pdf_pages[0],
                span=" | ".join(c for c in t.rows[i] if c),
                method="table_row",
                confidence=0.85,
            )
    return list(found.values())


def _monitoring_agency(doc: ParsedDocument) -> list[IssueFact]:
    appointed: tuple[int, str] | None = None
    not_required: tuple[int, str] | None = None
    for page in doc.pages:
        for b in page.blocks:
            text = " ".join(b.text.split())
            if appointed is None and (m := _APPOINTED.search(text)):
                appointed = (page.pdf_page, m.group(0))
            if not_required is None and (m := _NOT_REQUIRED.search(text)):
                not_required = (page.pdf_page, m.group(0))
    if bool(appointed) == bool(not_required):
        return []  # silence, or contradictory statements: no fact
    page_no, span = appointed or not_required  # type: ignore[misc]
    return [
        IssueFact(
            key=IssueKey.MONITORING_AGENCY_APPOINTED,
            value=Decimal(1 if appointed else 0),
            raw=span,
            pdf_page=page_no,
            span=span,
            method="regex",
            confidence=0.75,
        )
    ]


def extract_issue_facts(
    doc: ParsedDocument, *, max_page: int = DEFAULT_COVER_PAGES
) -> list[IssueFact]:
    """Issue sizes from the first `max_page` pages, objects and monitoring agency from anywhere."""
    return [*_cover_amounts(doc, max_page), *_objects_from_tables(doc), *_monitoring_agency(doc)]


__all__ = ["IssueFact", "IssueKey", "detect_unit", "extract_issue_facts"]
