"""
Financial label lexicon.

Each field has positive patterns with a strength (1.0 exact / defined term,
0.8 standard synonym, 0.6 weaker synonym) and negative patterns that veto a
match. Patterns run against a normalised label (lowercase, punctuation folded).

Deliberate exclusions (baseline defect D9): profit before tax, EBIT and EBITDA
are NOT operating profit; "cash and cash equivalents" alone is NOT monetary
assets; ratios, margins, growth rates, per-share figures and returns are never
matched to amount fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_GLOBAL_NEGATIVE = re.compile(
    r"(?:\bmargin\b|\bratio\b|\bgrowth\b|\breturn on\b|\bper share\b|\bper equity share\b|%|"
    r"\bpercentage\b|\bas a % of\b|\bcagr\b|\bturnover ratio\b|\bdays\b|\btimes\b|\(x\)|"
    r"\bweighted average\b|\bnumber of\b|\bbasic\b|\bdiluted\b|\beps\b)"
)


@dataclass(frozen=True)
class FieldDef:
    field: str  # fiscal-year field name
    positives: tuple[tuple[re.Pattern[str], float], ...]
    negatives: tuple[re.Pattern[str], ...] = ()
    allow_percent_context: bool = False


def _p(pattern: str, strength: float) -> tuple[re.Pattern[str], float]:
    return re.compile(pattern), strength


FIELDS: tuple[FieldDef, ...] = (
    FieldDef(
        "net_tangible_assets",
        (_p(r"^net tangible assets\b", 1.0), _p(r"\bnet tangible assets\b", 0.9)),
        (re.compile(r"\bmonetary assets\b"),),
    ),
    FieldDef(
        "monetary_assets",
        (_p(r"^monetary assets\b", 1.0), _p(r"\bmonetary assets\b", 0.9)),
        (re.compile(r"\bnet tangible assets\b"),),
    ),
    FieldDef(
        "operating_profit",
        (_p(r"^(?:restated )?operating profit\b", 1.0), _p(r"\boperating profit\b", 0.85)),
        (re.compile(r"before|\bebit|\bebitda\b|\bpbt\b|\btax\b|\bloss\b(?! )"),),
    ),
    FieldDef(
        "net_worth",
        (
            _p(r"^(?:restated )?net worth\b", 1.0),
            _p(r"\bnet worth\b", 0.9),
            _p(r"^total equity$", 0.7),
            _p(r"^(?:total )?shareholders? funds?$", 0.7),
            _p(r"^total equity attributable to (?:the )?(?:equity holders|owners)", 0.65),
        ),
        (re.compile(r"\breturn\b|\bronw\b|\bnon[- ]controlling\b|\bnci\b"),),
    ),
    FieldDef(
        "revenue",
        (
            _p(r"^(?:restated )?revenue from operations\b", 1.0),
            _p(r"\brevenue from operations\b", 0.85),
        ),
        (re.compile(r"\bother income\b|\btotal income\b"),),
    ),
    FieldDef(
        "pat",
        (
            _p(
                r"^(?:restated )?profit (?:/ ?\(loss\) )?(?:after tax|for the (?:year|period))\b",
                0.95,
            ),
            _p(r"^profit after tax\b", 1.0),
            _p(r"^net profit after tax\b", 0.9),
        ),
        (
            re.compile(
                r"non[- ]controlling|other comprehensive|attributable to non|discontinued|before"
            ),
        ),
    ),
    FieldDef("total_assets", (_p(r"^total assets$", 1.0),), (re.compile(r"\bnet\b|tangible"),)),
    FieldDef("total_liabilities", (_p(r"^total liabilities$", 1.0),), (re.compile(r"equity"),)),
    FieldDef(
        "paid_up_capital",
        (_p(r"^equity share capital$", 1.0), _p(r"^(?:paid[- ]up )?share capital$", 0.85)),
        (re.compile(r"authori[sz]ed|issued|preference"),),
    ),
    FieldDef(
        "reserves_and_surplus",
        (_p(r"^other equity$", 0.9), _p(r"^reserves (?:and|&) surplus$", 1.0)),
        (re.compile(r"non[- ]controlling"),),
    ),
    FieldDef(
        "ebitda",
        (_p(r"^(?:restated )?ebitda$", 1.0), _p(r"^earnings before interest,? tax", 0.8)),
        (),
    ),
)


def normalise_label(text: str) -> str:
    t = text.lower().replace("’", "'").replace("‘", "'")
    t = re.sub(r"\bas restated\b|\brestated\b", "restated", t)
    t = re.sub(r"[^a-z0-9%&/()'\- ]+", " ", t)
    t = re.sub(r"\(\s*[a-z0-9]{1,3}\s*\)$", "", t)  # trailing footnote (a)
    t = re.sub(r"[,:;]", " ", t)
    t = " ".join(t.split())
    t = re.sub(r"^restated (?=\w)", "restated ", t)
    return t.strip(" -")


@dataclass(frozen=True)
class LabelMatch:
    field: str
    strength: float
    label: str


def match_label(raw_label: str) -> LabelMatch | None:
    """Return the best field match for a row label, or None."""
    label = normalise_label(raw_label)
    if not label or len(label) > 160:
        return None
    best: LabelMatch | None = None
    for fd in FIELDS:
        strength = max((s for p, s in fd.positives if p.search(label)), default=0.0)
        if strength == 0.0:
            continue
        if any(n.search(label) for n in fd.negatives):
            continue
        if _GLOBAL_NEGATIVE.search(label) and not fd.allow_percent_context:
            continue
        if best is None or strength > best.strength:
            best = LabelMatch(fd.field, strength, label)
    return best
