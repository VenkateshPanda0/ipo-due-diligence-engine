"""Red-flag rule specifications (TOML files, one rule per file).

A rule says what to compute from which facts, how severe a hit is, why it matters in one
sentence, and where its threshold comes from. A regulatory threshold must name the clause and the
date it was checked; a heuristic threshold must say so and cite the literature that motivates it.
"""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Severity = Literal["info", "low", "medium", "high"]
Platform = Literal["mainboard", "sme"]


class Source(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["regulation", "enforcement", "literature", "heuristic"]
    ref: str
    clause: str | None = None
    url: str | None = None
    checked_on: date
    effective: date | None = None
    note: str = ""

    @model_validator(mode="after")
    def _regulation_needs_clause(self) -> Source:
        if self.kind == "regulation" and not self.clause:
            raise ValueError("a regulation source must name the clause")
        return self


class RatioVsCap(BaseModel):
    """sum(numerators) / denominator against a cap (optionally also an absolute cap in rupees)."""

    kind: Literal["ratio_vs_cap"]
    numerators: list[str] = Field(min_length=1)
    denominator: str
    cap: float
    near_cap_fraction: float = 0.9
    abs_cap: float | None = None  # rupees; effective cap is min(cap, abs_cap / denominator)


class RequiredIf(BaseModel):
    """If `trigger` exceeds `threshold`, `required` (1 = yes, 0 = no) must be 1."""

    kind: Literal["required_if"]
    trigger: str
    threshold: float
    required: str


class PersistentBelow(BaseModel):
    """`left` below `right` in at least `min_breaches` of the latest `min_periods` years."""

    kind: Literal["persistent_below"]
    left: str
    right: str
    min_periods: int = 3
    min_breaches: int = 2
    require_right_positive: bool = True


class GrowthGap(BaseModel):
    """Latest-year growth of `left` exceeds growth of `right` by at least `min_gap_pp` points."""

    kind: Literal["growth_gap"]
    left: str
    right: str
    min_gap_pp: float


Logic = Annotated[
    RatioVsCap | RequiredIf | PersistentBelow | GrowthGap, Field(discriminator="kind")
]


class RuleSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    rationale: str  # one sentence a banker can repeat
    platforms: list[Platform]
    severity: Severity
    heuristic: bool  # True: the threshold is ours, not the regulator's
    citation_requirement: str
    logic: Logic
    sources: list[Source] = Field(min_length=1)

    @model_validator(mode="after")
    def _sources_match_kind(self) -> RuleSpec:
        has_reg = any(s.kind in ("regulation", "enforcement") for s in self.sources)
        if not self.heuristic and not has_reg:
            raise ValueError("a non-heuristic rule must cite a regulation or enforcement source")
        return self


def load_rule_file(path: Path) -> RuleSpec:
    with path.open("rb") as f:
        return RuleSpec.model_validate(tomllib.load(f))
