"""Evaluate rules over cited facts. Pure Python; no flag is ever raised without citations."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field

from redherring.flags.spec import (
    GrowthGap,
    PersistentBelow,
    RatioVsCap,
    RequiredIf,
    RuleSpec,
    Severity,
    Source,
    load_rule_file,
)


class Citation(BaseModel):
    pdf_page: int
    span: str


class Fact(BaseModel):
    """A number the rules may use, with the evidence it was read from."""

    key: str
    value: Decimal
    citations: list[Citation] = Field(default_factory=list)


class Flag(BaseModel):
    rule_id: str
    rule_name: str
    severity: Severity
    explanation: str
    numbers: dict[str, Decimal]
    citations: list[Citation]
    sources: list[Source]
    heuristic: bool


Facts = dict[str, Fact]


def load_rules(directory: Path) -> list[RuleSpec]:
    return [load_rule_file(p) for p in sorted(directory.glob("*.toml"))]


def _usable(facts: Facts, keys: Iterable[str]) -> list[Fact] | None:
    """The facts for `keys`, or None if any is missing or uncited."""
    out: list[Fact] = []
    for k in keys:
        f = facts.get(k)
        if f is None or not f.citations:
            return None
        out.append(f)
    return out


def _cites(facts: Iterable[Fact]) -> list[Citation]:
    seen: set[tuple[int, str]] = set()
    out: list[Citation] = []
    for f in facts:
        for c in f.citations:
            if (c.pdf_page, c.span) not in seen:
                seen.add((c.pdf_page, c.span))
                out.append(c)
    return out


def _series(facts: Facts, prefix: str) -> dict[str, Fact]:
    p = prefix + "."
    return {k[len(p) :]: f for k, f in facts.items() if k.startswith(p) and f.citations}


def _flag(
    rule: RuleSpec,
    severity: Severity,
    explanation: str,
    numbers: dict[str, Decimal],
    used: Iterable[Fact],
) -> Flag:
    return Flag(
        rule_id=rule.id,
        rule_name=rule.name,
        severity=severity,
        explanation=explanation,
        numbers=numbers,
        citations=_cites(used),
        sources=list(rule.sources),
        heuristic=rule.heuristic,
    )


def _ratio_vs_cap(rule: RuleSpec, logic: RatioVsCap, facts: Facts) -> list[Flag]:
    used = _usable(facts, [*logic.numerators, logic.denominator])
    if used is None:
        return []
    *nums, den = used
    if den.value <= 0:
        return []
    numerator = sum((n.value for n in nums), Decimal(0))
    ratio = numerator / den.value
    cap = Decimal(str(logic.cap))
    if logic.abs_cap is not None:
        cap = min(cap, Decimal(str(logic.abs_cap)) / den.value)
    numbers = {"ratio": ratio, "cap": cap, "numerator": numerator, "denominator": den.value}
    if ratio > cap:
        text = (
            f"{rule.name}: {ratio:.0%} against a limit of {cap:.0%}; the figure is above the limit."
        )
        return [_flag(rule, "high", text, numbers, used)]
    if ratio >= cap * Decimal(str(logic.near_cap_fraction)):
        text = f"{rule.name}: {ratio:.0%} against a limit of {cap:.0%}, i.e. close to the limit."
        return [_flag(rule, rule.severity, text, numbers, used)]
    return []


def _required_if(rule: RuleSpec, logic: RequiredIf, facts: Facts) -> list[Flag]:
    used = _usable(facts, [logic.trigger, logic.required])
    if used is None:
        return []
    trigger, required = used
    if trigger.value > Decimal(str(logic.threshold)) and required.value == 0:
        text = (
            f"{rule.name}: the size ({trigger.value:,.0f}) is above the threshold of "
            f"{Decimal(str(logic.threshold)):,.0f} but the document states it is not in place."
        )
        numbers = {"size": trigger.value, "threshold": Decimal(str(logic.threshold))}
        return [_flag(rule, rule.severity, text, numbers, used)]
    return []


def _persistent_below(rule: RuleSpec, logic: PersistentBelow, facts: Facts) -> list[Flag]:
    left, right = _series(facts, logic.left), _series(facts, logic.right)
    periods = sorted(set(left) & set(right))[-logic.min_periods :]
    if len(periods) < logic.min_periods:
        return []
    breached = [
        p
        for p in periods
        if left[p].value < right[p].value
        and (right[p].value > 0 or not logic.require_right_positive)
    ]
    if len(breached) < logic.min_breaches:
        return []
    used = [f for p in periods for f in (left[p], right[p])]
    text = (
        f"{rule.name}: below in {len(breached)} of the last {len(periods)} years "
        f"({', '.join(breached)})."
    )
    numbers = {"breaches": Decimal(len(breached)), "periods": Decimal(len(periods))}
    return [_flag(rule, rule.severity, text, numbers, used)]


def _growth_gap(rule: RuleSpec, logic: GrowthGap, facts: Facts) -> list[Flag]:
    left, right = _series(facts, logic.left), _series(facts, logic.right)
    periods = sorted(set(left) & set(right))[-2:]
    if len(periods) < 2:
        return []
    p0, p1 = periods
    if left[p0].value <= 0 or right[p0].value <= 0:
        return []
    g_left = left[p1].value / left[p0].value - 1
    g_right = right[p1].value / right[p0].value - 1
    gap = (g_left - g_right) * 100
    if gap < Decimal(str(logic.min_gap_pp)):
        return []
    text = (
        f"{rule.name}: grew {g_left:.0%} against {g_right:.0%} ({p0} to {p1}), "
        f"a gap of {gap:.0f} percentage points."
    )
    numbers = {"growth_left": g_left, "growth_right": g_right, "gap_pp": gap}
    return [_flag(rule, rule.severity, text, numbers, [left[p0], left[p1], right[p0], right[p1]])]


def evaluate(rules: Iterable[RuleSpec], facts: Facts, *, platform: str) -> list[Flag]:
    """Run every rule that applies to `platform`; return the flags raised."""
    flags: list[Flag] = []
    for rule in rules:
        if platform not in rule.platforms:
            continue
        logic = rule.logic
        if isinstance(logic, RatioVsCap):
            flags += _ratio_vs_cap(rule, logic, facts)
        elif isinstance(logic, RequiredIf):
            flags += _required_if(rule, logic, facts)
        elif isinstance(logic, PersistentBelow):
            flags += _persistent_below(rule, logic, facts)
        else:
            flags += _growth_gap(rule, logic, facts)
    return flags
