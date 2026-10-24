"""Evaluate rules over cited facts. Pure Python; no flag is ever raised without citations."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

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


RULES_DIR = Path(__file__).parent / "rules"


def load_rules(directory: Path = RULES_DIR) -> list[RuleSpec]:
    return [load_rule_file(p) for p in sorted(directory.glob("*.toml"))]


def _missing(facts: Facts, keys: Iterable[str]) -> list[str]:
    return [k for k in keys if k not in facts or not facts[k].citations]


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


def _series(facts: Facts, prefix: str, period_regex: str) -> dict[str, Fact]:
    p = prefix + "."
    pattern = re.compile(period_regex)
    return {
        k[len(p) :]: f
        for k, f in facts.items()
        if k.startswith(p) and f.citations and pattern.match(k[len(p) :])
    }


class _Result(BaseModel):
    """What one rule did: flags raised, whether it could be evaluated, and the figures involved."""

    flags: list[Flag] = Field(default_factory=list)
    evaluated: bool = False
    numbers: dict[str, Decimal] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)
    detail: str = ""


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


def _ratio_vs_cap(rule: RuleSpec, logic: RatioVsCap, facts: Facts) -> _Result:
    keys = [*logic.numerators, logic.denominator]
    used = _usable(facts, keys)
    if used is None:
        return _Result(missing=_missing(facts, keys))
    *nums, den = used
    if den.value <= 0:
        return _Result(detail="denominator is not positive")
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
        return _Result(
            flags=[_flag(rule, "high", text, numbers, used)], evaluated=True, numbers=numbers
        )
    if ratio >= cap * Decimal(str(logic.near_cap_fraction)):
        text = f"{rule.name}: {ratio:.0%} against a limit of {cap:.0%}, i.e. close to the limit."
        flag = _flag(rule, rule.severity, text, numbers, used)
        return _Result(flags=[flag], evaluated=True, numbers=numbers)
    return _Result(evaluated=True, numbers=numbers)


def _required_if(rule: RuleSpec, logic: RequiredIf, facts: Facts) -> _Result:
    keys = [logic.trigger, logic.required]
    used = _usable(facts, keys)
    if used is None:
        return _Result(missing=_missing(facts, keys))
    trigger, required = used
    threshold = Decimal(str(logic.threshold))
    numbers = {"size": trigger.value, "threshold": threshold, "required_present": required.value}
    if trigger.value > threshold and required.value == 0:
        text = (
            f"{rule.name}: the size ({trigger.value:,.0f}) is above the threshold of "
            f"{threshold:,.0f} but the document states it is not in place."
        )
        flag = _flag(rule, rule.severity, text, numbers, used)
        return _Result(flags=[flag], evaluated=True, numbers=numbers)
    return _Result(evaluated=True, numbers=numbers)


def _persistent_below(rule: RuleSpec, logic: PersistentBelow, facts: Facts) -> _Result:
    left = _series(facts, logic.left, logic.period_regex)
    right = _series(facts, logic.right, logic.period_regex)
    periods = sorted(set(left) & set(right))[-logic.min_periods :]
    if len(periods) < logic.min_periods:
        return _Result(
            missing=[logic.left, logic.right],
            detail=f"needs {logic.min_periods} common periods of both series; have {len(periods)}",
        )
    breached = [
        p
        for p in periods
        if left[p].value < right[p].value
        and (right[p].value > 0 or not logic.require_right_positive)
    ]
    numbers = {"breaches": Decimal(len(breached)), "periods": Decimal(len(periods))}
    if len(breached) < logic.min_breaches:
        return _Result(evaluated=True, numbers=numbers)
    used = [f for p in periods for f in (left[p], right[p])]
    text = (
        f"{rule.name}: below in {len(breached)} of the last {len(periods)} years "
        f"({', '.join(breached)})."
    )
    flag = _flag(rule, rule.severity, text, numbers, used)
    return _Result(flags=[flag], evaluated=True, numbers=numbers)


def _growth_gap(rule: RuleSpec, logic: GrowthGap, facts: Facts) -> _Result:
    left = _series(facts, logic.left, logic.period_regex)
    right = _series(facts, logic.right, logic.period_regex)
    periods = sorted(set(left) & set(right))[-2:]
    if len(periods) < 2:
        return _Result(
            missing=[logic.left, logic.right],
            detail=f"needs 2 common periods of both series; have {len(periods)}",
        )
    p0, p1 = periods
    if left[p0].value <= 0 or right[p0].value <= 0:
        return _Result(detail="base-period value is not positive")
    g_left = left[p1].value / left[p0].value - 1
    g_right = right[p1].value / right[p0].value - 1
    gap = (g_left - g_right) * 100
    numbers = {"growth_left": g_left, "growth_right": g_right, "gap_pp": gap}
    if gap < Decimal(str(logic.min_gap_pp)):
        return _Result(evaluated=True, numbers=numbers)
    text = (
        f"{rule.name}: grew {g_left:.0%} against {g_right:.0%} ({p0} to {p1}), "
        f"a gap of {gap:.0f} percentage points."
    )
    used = [left[p0], left[p1], right[p0], right[p1]]
    return _Result(
        flags=[_flag(rule, rule.severity, text, numbers, used)], evaluated=True, numbers=numbers
    )


def _run(rule: RuleSpec, facts: Facts) -> _Result:
    logic = rule.logic
    if isinstance(logic, RatioVsCap):
        return _ratio_vs_cap(rule, logic, facts)
    if isinstance(logic, RequiredIf):
        return _required_if(rule, logic, facts)
    if isinstance(logic, PersistentBelow):
        return _persistent_below(rule, logic, facts)
    return _growth_gap(rule, logic, facts)


AuditStatus = Literal["flagged", "clear", "missing_inputs", "other_platform", "not_in_force"]


class RuleAudit(BaseModel):
    """Why a rule did or did not decide anything for one document."""

    rule_id: str
    status: AuditStatus
    numbers: dict[str, Decimal] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)
    detail: str = ""


def audit(
    rules: Iterable[RuleSpec], facts: Facts, *, platform: str, as_of: date | None = None
) -> list[RuleAudit]:
    """One entry per rule: flagged, clear (with its figures), or why it was not decisive."""
    day = as_of or date.today()
    out: list[RuleAudit] = []
    for rule in rules:
        if platform not in rule.platforms:
            out.append(RuleAudit(rule_id=rule.id, status="other_platform"))
        elif not rule.applies_on(day):
            out.append(RuleAudit(rule_id=rule.id, status="not_in_force"))
        else:
            r = _run(rule, facts)
            status: AuditStatus = (
                "flagged" if r.flags else ("clear" if r.evaluated else "missing_inputs")
            )
            out.append(
                RuleAudit(
                    rule_id=rule.id,
                    status=status,
                    numbers=r.numbers,
                    missing=r.missing,
                    detail=r.detail,
                )
            )
    return out


def evaluate(
    rules: Iterable[RuleSpec], facts: Facts, *, platform: str, as_of: date | None = None
) -> list[Flag]:
    """Run every rule that applies to `platform`; return the flags raised.

    `as_of` is the document's date: only rule versions in force that day are applied. Without it
    only rules in force today are used, so a superseded threshold is never applied by accident.
    """
    day = as_of or date.today()
    flags: list[Flag] = []
    for rule in rules:
        if platform in rule.platforms and rule.applies_on(day):
            flags += _run(rule, facts).flags
    return flags
