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
from redherring.verify.footing import quantum

DEFAULT_COVER_PAGES = 40


class IssueKey(StrEnum):
    FRESH_ISSUE_AMOUNT = "issue.fresh_issue_amount"
    OFS_AMOUNT = "issue.ofs_amount"
    TOTAL_ISSUE_AMOUNT = "issue.total_issue_amount"
    GCP_AMOUNT = "objects.gcp_amount"
    UNIDENTIFIED_ACQUISITION_AMOUNT = "objects.unidentified_acquisition_amount"
    DEBT_REPAYMENT_AMOUNT = "objects.debt_repayment_amount"
    MONITORING_AGENCY_APPOINTED = "objects.monitoring_agency_appointed"
    ELIGIBILITY_REG_6_2 = "issue.eligibility_reg_6_2"  # 1: made under Reg 6(2), 0: under Reg 6(1)


class IssueFact(BaseModel):
    key: IssueKey
    value: Decimal = Field(description="Rupees for amounts; 1 or 0 for yes/no facts")
    raw: str = Field(description="The figure or phrase exactly as printed")
    unit: Unit | None = None
    pdf_page: int
    span: str = Field(description="Text the fact was read from")
    parts: list[str] = Field(
        default_factory=list,
        description="For a sum of printed figures: each part as printed (raw is then the first)",
    )
    method: str
    confidence: float = Field(ge=0.0, le=1.0)


_AMT = r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*\**\s*(million|mn|lakhs?|lacs?|crores?|cr)\b"
# Up to 1200 characters, never crossing a sentence end (". " + capital) or another "aggregating":
# the first "aggregating" after the phrase belongs to it. A mention that is itself a quoted
# defined term, as in (“Offer for Sale”), is skipped: the amount precedes it, not follows it.
_GAP = r"(?:(?!\.\s+[A-Z])(?!aggregat).){0,1200}?"
# Laid-out covers flatten a "Fresh issue | Offer for sale" table into one run of text, so an amount
# found after crossing into the other role's wording belongs to that other role.
# A pre-IPO or private placement is a separate raise: its amount is not the offer's
_NOT_PLACEMENT = r"(?!pre-?\s*ipo)(?!private\s+placement)"
_GAP_NO_OFS = rf"(?:(?!\.\s+[A-Z])(?!aggregat)(?!offer\s+for\s+sale){_NOT_PLACEMENT}.){{0,1200}}?"
_GAP_NO_FRESH = rf"(?:(?!\.\s+[A-Z])(?!aggregat)(?!fresh\s+issue){_NOT_PLACEMENT}.){{0,1200}}?"
_NOT_DEFINED = r"(?<![“\"(])"
_FRESH = re.compile(
    rf"{_NOT_DEFINED}fresh\s+issue\b{_GAP_NO_OFS}aggregat\w*\s*(?:to\s+|up\s+to\s+)?{_AMT}", re.I
)
_OFS = re.compile(
    rf"{_NOT_DEFINED}offer\s+for\s+sale\b{_GAP_NO_FRESH}aggregat\w*\s*(?:to\s+|up\s+to\s+)?{_AMT}",
    re.I,
)
# "... aggregating to Rs. 5,000.00 million (the "Issue" or "Fresh Issue")": the amount comes first
# and the defined term after it says what the amount is. `_roles` reads that term; "Offer Price"
# and other terms are not roles.
_DEFINED_AFTER = re.compile(
    rf"aggregat\w*\s*(?:to\s+|up\s+to\s+)?{_AMT}\s*\(([^)]{{1,80}})\)", re.I
)


# "... aggregating up to ₹7,000 million comprising a fresh issue ...": the amount before
# "comprising" is the whole offer even when no defined term follows it.
_TOTAL_COMPRISING = re.compile(
    rf"aggregat\w*\s*(?:to\s+|up\s+to\s+)?{_AMT}\s*(?:\([^)]{{1,40}}\)\s*)?"
    r"comprising\s+(?:of\s+)?(?:a\s+)?fresh\s+issue",
    re.I,
)
# SME covers: a header "Fresh Issue Size | OFS Size | Total Issue Size" over one row
# "Fresh Issue ₹1,301.04 Lakhs | Nil | ₹1,301.04 Lakhs".
_RAW_AMT = r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(million|mn|lakhs?|lacs?|crores?|cr)\b"
_TYPE_ROW = re.compile(
    rf"\bfresh\s+issue\s+{_RAW_AMT}\s+(?:(nil|n\.?\s?a\.?)|{_RAW_AMT})\s+{_RAW_AMT}", re.I
)


def _roles(term: str) -> set[IssueKey]:
    words = re.sub(r"[“”\"'*]", "", term).lower().split()
    if words[:1] == ["the"]:
        words = words[1:]
    roles: set[IssueKey] = set()
    if words in (["offer"], ["issue"], ["public", "issue"]) or (
        words[:1] in (["offer"], ["issue"]) and "or" in words
    ):
        roles.add(IssueKey.TOTAL_ISSUE_AMOUNT)
    if "fresh issue" in " ".join(words):
        roles.add(IssueKey.FRESH_ISSUE_AMOUNT)
    if " ".join(words) == "offer for sale":
        roles.add(IssueKey.OFS_AMOUNT)
    return roles


_ELIGIBILITY = re.compile(r"made\s+pursuant\s+to\s+Regulation\s+6\s*\(\s*([12])\s*\)\s+of", re.I)

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
    r"|\bmonitoring\s+agency\b(?:(?!\.\s+[A-Z]).){0,80}?(?:has|have)\s+been\s+appointed"
    r"|(?:has|have)\s+appointed\s+(?:(?!\.\s+[A-Z]).){0,160}?\bto\s+monitor\s+(?:the\s+)?"
    r"(?:utili[sz]ation|use|deployment)",
    re.I,
)
_NOT_REQUIRED = re.compile(
    r"\bno\s+monitoring\s+agency\b"
    r"|(?:has|have)\s+not\s+appointed\s+(?:any\s+|a\s+)?monitoring\s+agency\b"
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


def _fact(
    key: IssueKey, amount: tuple[Decimal, str, Unit], page: int, span: str, conf: float
) -> IssueFact:
    value, raw, unit = amount
    return IssueFact(
        key=key,
        value=value,
        raw=raw,
        unit=unit,
        pdf_page=page,
        span=span,
        method="regex",
        confidence=conf,
    )


def _step(f: IssueFact) -> Decimal:
    return quantum(f.raw) * MULTIPLIER[f.unit] if f.unit else Decimal(1)


def _by_value(cands: list[IssueFact]) -> dict[Decimal, list[IssueFact]]:
    out: dict[Decimal, list[IssueFact]] = {}
    for c in cands:  # document order: the first fact of a value is its earliest mention
        out.setdefault(c.value, []).append(c)
    return out


def _resolve(cands: dict[IssueKey, list[IssueFact]]) -> dict[IssueKey, IssueFact]:
    """One fact per key out of every candidate found on the cover pages.

    Cover tables flatten into text in which a column's amount follows another column's heading, so
    the first amount after "Offer for Sale" can be the fresh issue's. Where fresh, offer for sale
    and total are all present, the combination that adds up (fresh + OFS = total) wins, weighted
    by how often each figure is printed. Otherwise each key takes its most frequently printed
    value, earliest first on a tie.
    """
    groups = {k: _by_value(v) for k, v in cands.items()}
    chosen: dict[IssueKey, Decimal] = {}
    trio = (IssueKey.FRESH_ISSUE_AMOUNT, IssueKey.OFS_AMOUNT, IssueKey.TOTAL_ISSUE_AMOUNT)
    if all(k in groups for k in trio):
        best = -1
        for f, fs in groups[trio[0]].items():
            for o, os_ in groups[trio[1]].items():
                for t, ts in groups[trio[2]].items():
                    tol = 2 * max(_step(fs[0]), _step(os_[0]), _step(ts[0]))
                    score = len(fs) + len(os_) + len(ts)
                    if abs(f + o - t) <= tol and score > best:
                        best, chosen = score, {trio[0]: f, trio[1]: o, trio[2]: t}
    for key, by_value in groups.items():
        if key not in chosen:
            chosen[key] = max(by_value, key=lambda v: len(by_value[v]))  # first max = earliest
    return {key: groups[key][value][0] for key, value in chosen.items()}


_COVER_ORDER = re.compile(r"fresh.*offer\s+for\s+sale.*total", re.I | re.S)


def _row_text(row: list[str]) -> str:
    return " ".join(" ".join(c for c in row if c).split())


def _cover_table_rows(doc: ParsedDocument, max_page: int) -> tuple[list[IssueFact], set[str]]:
    """Fresh / offer-for-sale / total from a cover table read by column.

    The standard cover table has the columns "Fresh Issue size | Offer for Sale size | Total Offer
    size" and one row "Fresh Issue and Offer for Sale | cell | cell | cell". Read as flattened text,
    a "[●]" cell lets the next amount slide into the wrong role (Lenskart: the fresh issue's
    ₹21,500 million became the offer for sale as well). Here the three cells after the type cell
    are fresh, offer for sale and total, in that order, when the rows above name the columns in
    that order. Returns the facts and the row texts handled, so the text readers skip them.
    """
    facts: list[IssueFact] = []
    handled: set[str] = set()
    for t in doc.tables:
        if t.pdf_pages[0] > max_page:
            continue
        for i, row in enumerate(t.rows):
            first = row[0].lower() if row else ""
            if "fresh issue" not in first or "offer for sale" not in first:
                continue
            above = t.rows[max(0, i - 5) : i]
            width = max((len(r) for r in above), default=0)
            # column by column: a header split over rows ("OFFER" / "FOR SALE") reads in order
            head = " ".join(
                " ".join(r[j] for r in above if j < len(r) and r[j]) for j in range(width)
            )
            cells = [c for c in row[1:] if c.strip()]
            slots = [c for c in cells if "aggregat" in c.lower()][:3]
            if len(slots) < 3 or not _COVER_ORDER.search(head):
                continue
            page = t.row_pages[i] if i < len(t.row_pages) else t.pdf_pages[0]
            text = _row_text(row)
            handled.add(text)
            for key, cell in zip(
                (IssueKey.FRESH_ISSUE_AMOUNT, IssueKey.OFS_AMOUNT, IssueKey.TOTAL_ISSUE_AMOUNT),
                slots,
                strict=True,
            ):
                m = re.search(_AMT, " ".join(cell.split()), re.I)
                if m and (amount := _amount(m)):
                    facts.append(_fact(key, amount, page, " ".join(cell.split())[:200], 0.9))
    return facts, handled


def _cover_amounts(doc: ParsedDocument, max_page: int) -> list[IssueFact]:
    cands: dict[IssueKey, list[IssueFact]] = {}
    row_na: dict[int, bool] = {}

    def add(fact: IssueFact) -> None:
        cands.setdefault(fact.key, []).append(fact)

    positional, handled = _cover_table_rows(doc, max_page)
    for fact in positional:
        add(fact)
    for page, text in _segments(doc, max_page):
        if text in handled:
            continue  # read by column above
        for dm in _DEFINED_AFTER.finditer(text):
            amount = _amount(dm)
            if amount:
                span = text[max(0, dm.start() - 40) : dm.end() + 20]
                for role in _roles(dm.group(3)):
                    add(_fact(role, amount, page, span, 0.85))
        for tm in _TOTAL_COMPRISING.finditer(text):
            amount = _amount(tm)
            if amount:
                span = text[max(0, tm.start() - 40) : tm.end() + 20]
                add(_fact(IssueKey.TOTAL_ISSUE_AMOUNT, amount, page, span, 0.8))
        if tr := _TYPE_ROW.search(text):
            span = text[max(0, tr.start() - 40) : tr.end() + 20]
            for key, groups in (
                (IssueKey.FRESH_ISSUE_AMOUNT, (1, 2)),
                (IssueKey.OFS_AMOUNT, (4, 5)),
                (IssueKey.TOTAL_ISSUE_AMOUNT, (6, 7)),
            ):
                num, unit_word = tr.group(groups[0]), tr.group(groups[1])
                value = _num(num) if num else None
                unit = _UNIT_WORDS.get(unit_word.lower()) if unit_word else None
                if value is not None and unit is not None:
                    add(_fact(key, (value * MULTIPLIER[unit], num, unit), page, span, 0.85))
        for key, pattern in ((IssueKey.FRESH_ISSUE_AMOUNT, _FRESH), (IssueKey.OFS_AMOUNT, _OFS)):
            for m in pattern.finditer(text):
                amount = _amount(m)
                if amount:
                    span = text[max(0, m.start() - 40) : m.end() + 20]
                    add(_fact(key, amount, page, span, 0.8))
                    if key is IssueKey.FRESH_ISSUE_AMOUNT:
                        row_na[page] = bool(_NOT_APPLICABLE.search(text[m.end() :]))
    found = _resolve(cands)
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


def _is_debt_repayment(label: str) -> bool:
    return bool(re.search(r"re-?pay|pre-?pay", label)) and bool(
        re.search(r"borrowing|debt|loan|indebtedness", label)
    )


def _debt_total(amounts: list[Decimal]) -> Decimal:
    """Sum of the repayment rows, unless one of them already is the total of the others."""
    total = sum(amounts, Decimal(0))
    for a in amounts:
        if len(amounts) > 1 and abs(total - a - a) <= Decimal("0.02"):
            return a
    return total


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
            # at least two uses of funds, all positive: a lone "repayment" line and its total, or
            # negative cash-flow lines, are not an objects table
            return (
                len(amounts) >= 2
                and all(a > 0 for a in amounts)
                and abs(sum(amounts, Decimal(0)) - amount[0]) <= Decimal("0.02")
            )
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
        debt: list[tuple[int, Decimal, str]] = []
        for i, (label, cells) in split:
            if _is_debt_repayment(label):
                if (amount := _first_amount(cells)) is not None:
                    debt.append((i, amount[0], amount[1]))
                continue
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
        if debt and IssueKey.DEBT_REPAYMENT_AMOUNT not in found:
            first = debt[0][0]
            found[IssueKey.DEBT_REPAYMENT_AMOUNT] = IssueFact(
                key=IssueKey.DEBT_REPAYMENT_AMOUNT,
                value=_debt_total([d[1] for d in debt]) * MULTIPLIER[unit],
                raw=debt[0][2],
                parts=[d[2] for d in debt] if len(debt) > 1 else [],
                unit=unit,
                pdf_page=t.row_pages[first] if first < len(t.row_pages) else t.pdf_pages[0],
                # a long row label must not push a later row's figure out of the cited span
                span=" || ".join(f"{t.rows[d[0]][0][:80]} | {d[2]}" for d in debt),
                method="table_row",
                confidence=0.85,
            )
    return list(found.values())


def _eligibility_route(doc: ParsedDocument, max_page: int) -> list[IssueFact]:
    for page, text in _segments(doc, max_page):
        if m := _ELIGIBILITY.search(text):
            return [
                IssueFact(
                    key=IssueKey.ELIGIBILITY_REG_6_2,
                    value=Decimal(1 if m.group(1) == "2" else 0),
                    raw=m.group(0),
                    pdf_page=page,
                    span=m.group(0),
                    method="regex",
                    confidence=0.85,
                )
            ]
    return []


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
    return [
        *_cover_amounts(doc, max_page),
        *_eligibility_route(doc, max_page),
        *_objects_from_tables(doc),
        *_monitoring_agency(doc),
    ]


__all__ = ["IssueFact", "IssueKey", "detect_unit", "extract_issue_facts"]
