"""
Financial number and unit normalisation.

Conventions (all explicit, all tested):
  * Indian grouping ``12,34,56,789`` and international ``123,456,789`` are both
    accepted; grouping must be well formed for one of the two systems.
  * Negatives: ``(1,234)``, ``-1,234``, ``1,234-`` (trailing minus), ``−1,234``
    (Unicode minus) and ``(1,234.5)``.
  * Dash / ``NA`` / ``N/A`` / ``nil`` / ``[●]`` are *null markers*: they mean "no
    value" and are never converted to zero.
  * A unit is never guessed: normalisation to ₹ crore requires an explicit unit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

CANONICAL_UNIT = "INR_CRORE"

# multiplier converting 1 unit of X into ₹ crore
UNIT_TO_CRORE: dict[str, Decimal] = {
    "INR": Decimal("0.0000001"),
    "INR_THOUSAND": Decimal("0.0001"),
    "INR_LAKH": Decimal("0.01"),
    "INR_MILLION": Decimal("0.1"),
    "INR_CRORE": Decimal("1"),
    "INR_BILLION": Decimal("100"),
}

_NULL_MARKERS = frozenset(
    {
        "-",
        "–",
        "—",
        "−",
        "--",
        "na",
        "n.a.",
        "n.a",
        "n/a",
        "nil",
        "none",
        "[●]",
        "[•]",
        "●",
        "•",
        "*",
    }
)
_DASHES = "‐‑‒–—−"
_CURRENCY_RE = re.compile(r"^(?:₹|rs\.?|inr|`)\s*", re.IGNORECASE)
_INDIAN_RE = re.compile(r"^\d{1,2}(?:,\d{2})*,\d{3}$")
_INTL_RE = re.compile(r"^\d{1,3}(?:,\d{3})+$")
_PLAIN_RE = re.compile(r"^\d+$")
_FOOTNOTE_RE = re.compile(r"(?:\(\d{1,2}\)|\*{1,3}|#{1,2}|\^|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)$")

NUMBER_TOKEN_RE = re.compile(r"\(?[-−–]?\s*(?:₹|Rs\.?|INR)?\s*\d[\d,]*(?:\.\d+)?\s*%?\)?-?")


@dataclass(frozen=True)
class ParsedNumber:
    """Result of parsing one numeric token."""

    original: str
    value: Decimal | None
    is_null_marker: bool = False
    is_percent: bool = False
    negative_by: str | None = None  # "parentheses" | "sign" | "trailing_minus"
    grouping: str | None = None  # "indian" | "international" | "none"
    warnings: tuple[str, ...] = ()


def parse_number(token: str) -> ParsedNumber:
    """Parse a financial number token. Unparseable input gives value=None."""
    original = token
    s = token.strip()
    for ch in _DASHES:
        s = s.replace(ch, "-")
    s = s.replace(" ", " ").strip()
    if s.lower().strip(" .") in _NULL_MARKERS or s.lower() in _NULL_MARKERS or s == "":
        return ParsedNumber(original, None, is_null_marker=s != "")
    warnings: list[str] = []
    negative_by: str | None = None
    footnote = re.match(r"^(.*\d)\s*\((?:\d{1,2}|[a-z]|[ivx]{1,4})\)$", s)
    if footnote and not s.startswith("("):
        s = footnote.group(1)
        warnings.append("footnote marker removed")
    if s.startswith("(") and s.endswith(")"):
        s, negative_by = s[1:-1].strip(), "parentheses"
    elif s.startswith("(") or s.endswith(")"):
        warnings.append("unbalanced parenthesis")
        s = s.strip("()").strip()
    if s.endswith("-") and len(s) > 1 and s[-2].isdigit():
        s, negative_by = s[:-1].strip(), "trailing_minus"
    if s.startswith("-"):
        if negative_by:
            warnings.append("multiple negative markers")
        s, negative_by = s[1:].strip(), "sign"
    s = _CURRENCY_RE.sub("", s).strip()
    if s.startswith("-") and negative_by is None:
        s, negative_by = s[1:].strip(), "sign"
    is_percent = s.endswith("%")
    if is_percent:
        s = s[:-1].strip()
    stripped = _FOOTNOTE_RE.sub("", s)
    if stripped != s and stripped and stripped[-1].isdigit():
        warnings.append("footnote marker removed")
        s = stripped
    s = s.replace(" ", "")
    if not s or not s[0].isdigit():
        return ParsedNumber(original, None, warnings=tuple(warnings + ["not a number"]))
    int_part, _, frac = s.partition(".")
    if frac and not frac.isdigit():
        return ParsedNumber(original, None, warnings=tuple(warnings + ["invalid decimal part"]))
    if "," in int_part:
        if _INDIAN_RE.match(int_part) and _INTL_RE.match(int_part):
            grouping = "international"  # e.g. 100,000 — identical in both systems
        elif _INDIAN_RE.match(int_part):
            grouping = "indian"
        elif _INTL_RE.match(int_part):
            grouping = "international"
        else:
            return ParsedNumber(
                original, None, warnings=tuple(warnings + ["malformed digit grouping"])
            )
    elif _PLAIN_RE.match(int_part):
        grouping = "none"
    else:
        return ParsedNumber(original, None, warnings=tuple(warnings + ["not a number"]))
    try:
        value = Decimal(int_part.replace(",", "") + (f".{frac}" if frac else ""))
    except InvalidOperation:
        return ParsedNumber(original, None, warnings=tuple(warnings + ["not a number"]))
    if negative_by:
        value = -value
    return ParsedNumber(original, value, False, is_percent, negative_by, grouping, tuple(warnings))


_UNIT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?:₹|rs\.?|inr|rupees)\s*(?:in\s+)?(?:'?000|thousands?)\b|in\s+(?:₹|rs\.?|inr)?\s*thousands?|\(\s*(?:₹|rs\.?|inr)\s*'000\s*\)",
            re.I,
        ),
        "INR_THOUSAND",
    ),
    (re.compile(r"\b[lti1]akhs?\b|\blacs?\b", re.I), "INR_LAKH"),  # tolerate OCR l→t/1/i
    (re.compile(r"\bmillions?\b|\bmn\b", re.I), "INR_MILLION"),
    (re.compile(r"\bcrores?\b|\bcr\.?\b", re.I), "INR_CRORE"),
    (re.compile(r"\bbillions?\b|\bbn\b", re.I), "INR_BILLION"),
)
# "₹ 30 million", "10 lakhs", "₹1,000,000 crore": an amount in prose, not a unit declaration.
_AMOUNT_PHRASE_RE = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(?:[lti1]akhs?|lacs?|millions?|mn|crores?|cr\.?|billions?|bn|thousands?)\b",
    re.I,
)
_UNIT_CONTEXT_RE = re.compile(
    r"₹|[@%?]\s*in\b|\brs\.?|\binr\b|\brupees\b|\bamounts?\b|\bfigures?\b|\bin\b", re.I
)


def detect_unit(text: str) -> str | None:
    """Detect a declared monetary unit in a header / caption, e.g. '(₹ in lakhs)'.

    Returns None unless a unit word appears together with a currency / 'in'
    context. Multiple distinct units in one text return None (ambiguous).
    """
    if not text:
        return None
    lowered = _AMOUNT_PHRASE_RE.sub(" ", text.lower())
    short_caption = re.fullmatch(r"\s*\([^()]{1,24}\)\s*", lowered) is not None
    if not short_caption and not _UNIT_CONTEXT_RE.search(lowered):
        return None
    found = {unit for pattern, unit in _UNIT_PATTERNS if pattern.search(lowered)}
    if len(found) == 1:
        return found.pop()
    if len(found) > 1:
        return None
    if re.search(r"\(\s*(?:₹|rs\.?|inr)\s*\)", lowered):
        return "INR"
    return None


def to_crore(value: Decimal, unit: str) -> Decimal:
    """Convert an amount in ``unit`` to ₹ crore exactly."""
    try:
        factor = UNIT_TO_CRORE[unit]
    except KeyError as exc:
        raise ValueError(f"Unknown unit '{unit}'.") from exc
    return value * factor


def find_number_tokens(text: str) -> list[tuple[str, int, int]]:
    """Return (token, start, end) for number-like tokens in a line of text."""
    out: list[tuple[str, int, int]] = []
    for m in NUMBER_TOKEN_RE.finditer(text):
        tok = m.group(0).strip()
        if any(ch.isdigit() for ch in tok):
            out.append((tok, m.start(), m.end()))
    return out
