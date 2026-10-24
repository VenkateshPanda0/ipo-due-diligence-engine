"""What changed between two versions of the same offering (draft, updated draft, RHP, prospectus).

Only figures the rules can use are compared (issue and objects facts, annual financials), each
within the coarser printed precision, so a restatement shows up and a re-rounding does not.
Nothing here says why a figure moved; it says that it did, with both pages to read.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from redherring.analyze import AnalysisReport, FactRecord

Kind = Literal["same", "changed", "added", "removed"]


class FactChange(BaseModel):
    key: str
    kind: Kind
    old: FactRecord | None = None
    new: FactRecord | None = None
    pct: Decimal | None = None  # (new - old) / |old| in percent, when both exist and old != 0


class FlagChange(BaseModel):
    rule_id: str
    kind: Literal["added", "removed", "kept"]


class Diff(BaseModel):
    changes: list[FactChange]
    flags: list[FlagChange]

    @property
    def period_only(self) -> list[FactChange]:
        """Financial figures for a period one version has and the other lacks: a new stub period or
        a year dropped from the window is expected, not a change in any figure."""
        return [c for c in self.changes if c.kind in ("added", "removed") and _is_financial(c.key)]

    @property
    def comparable(self) -> list[FactChange]:
        one_sided = {c.key for c in self.period_only}
        return [c for c in self.changes if c.key not in one_sided]

    @property
    def moved(self) -> list[FactChange]:
        return [c for c in self.comparable if c.kind != "same"]


def _is_financial(key: str) -> bool:
    return key.startswith("financials.")


def _compare(key: str, old: FactRecord | None, new: FactRecord | None) -> FactChange:
    if old is None:
        return FactChange(key=key, kind="added", new=new)
    if new is None:
        return FactChange(key=key, kind="removed", old=old)
    if abs(new.value - old.value) <= max(old.step, new.step):
        return FactChange(key=key, kind="same", old=old, new=new)
    pct = (new.value - old.value) / abs(old.value) * 100 if old.value != 0 else None
    return FactChange(key=key, kind="changed", old=old, new=new, pct=pct)


def diff_reports(old: AnalysisReport, new: AnalysisReport) -> Diff:
    a = {f.key: f for f in old.facts}
    b = {f.key: f for f in new.facts}
    changes = [_compare(k, a.get(k), b.get(k)) for k in sorted(a.keys() | b.keys())]
    fa, fb = {f.rule_id for f in old.flags}, {f.rule_id for f in new.flags}
    flags = [
        FlagChange(rule_id=r, kind="removed" if r not in fb else "added" if r not in fa else "kept")
        for r in sorted(fa | fb)
    ]
    return Diff(changes=changes, flags=flags)
