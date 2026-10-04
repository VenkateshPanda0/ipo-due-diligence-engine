"""
backend/app/regulatory/registry.py

Regulatory source-of-truth loader.

Legal metadata (sources, provisions, thresholds, verification status) lives in
versioned JSON under ``data/``. Rule code reads its parameters from the active
ruleset, so a threshold change is a reviewed data change that produces a new
ruleset version — never an in-place edit of a historical version.

This module MUST NOT import from app.rules, app.parser, app.api, app.engine.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LegalCategory, ListingRoute, RuleCategory, VerificationStatus

_DATA_DIR = Path(__file__).parent / "data"
CURRENT_RULESET_VERSION = "2.0.0"


class RegulatorySource(BaseModel):
    """An entry in the regulatory source register."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    title: str
    issuer: str
    kind: str
    url: str | None = None
    document_url: str | None = None
    document_sha256: str | None = None
    publication_date: date | None = None
    accessed_on: date | None = None
    notes: str = ""


class RuleSpec(BaseModel):
    """Legal metadata and parameters for one executable rule."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    rule_version: str
    name: str
    category: RuleCategory
    legal_category: LegalCategory
    routes: list[ListingRoute]
    source_ids: list[str]
    instrument: str
    provision: str
    source_url: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    applicability: str
    required_inputs: list[str]
    decision_procedure: str
    parameters: dict[str, str] = Field(default_factory=dict)
    evidence_requirements: str
    limitations: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus
    review_notes: list[str] = Field(default_factory=list)

    def decimal(self, name: str) -> Decimal:
        """Return a numeric parameter as Decimal (supports 'a/b' fractions)."""
        raw = self.parameters[name]
        if "/" in raw:
            frac = Fraction(raw)
            return Decimal(frac.numerator) / Decimal(frac.denominator)
        return Decimal(raw)

    def fraction(self, name: str) -> Fraction:
        """Return a parameter as an exact Fraction."""
        return Fraction(self.parameters[name])

    def integer(self, name: str) -> int:
        """Return an integer parameter."""
        return int(self.parameters[name])


class LegalReviewRecord(BaseModel):
    """Record of professional legal review for a ruleset."""

    model_config = ConfigDict(frozen=True)

    confirmed: bool = False
    reviewed_rule_ids: list[str] = Field(default_factory=list)
    reference: str | None = None


class Ruleset(BaseModel):
    """A versioned, immutable set of rule specifications."""

    model_config = ConfigDict(frozen=True)

    version: str
    status: str
    effective_from: date
    effective_to: date | None = None
    activated_on: date | None = None
    description: str
    supported_routes: list[ListingRoute]
    unsupported_routes: list[ListingRoute]
    legal_review: LegalReviewRecord
    change_summary: list[str]
    rules: list[RuleSpec] = Field(default_factory=list)

    def spec(self, rule_id: str) -> RuleSpec:
        """Return the spec for a rule ID."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        raise KeyError(f"Rule '{rule_id}' is not defined in ruleset {self.version}.")


def _load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        data: dict[str, object] = json.load(handle)
    return data


@lru_cache(maxsize=1)
def load_sources() -> dict[str, RegulatorySource]:
    """Load the regulatory source register keyed by source_id."""
    raw = _load_json(_DATA_DIR / "sources.json")
    items = raw["sources"]
    assert isinstance(items, list)
    sources = [RegulatorySource.model_validate(item) for item in items]
    return {s.source_id: s for s in sources}


def available_ruleset_versions() -> list[str]:
    """Return all ruleset versions present on disk."""
    return sorted(p.stem for p in (_DATA_DIR / "rulesets").glob("*.json"))


@lru_cache(maxsize=8)
def load_ruleset(version: str = CURRENT_RULESET_VERSION) -> Ruleset:
    """Load an executable ruleset. Superseded rulesets without specs are rejected."""
    path = _DATA_DIR / "rulesets" / f"{version}.json"
    if not path.is_file():
        raise KeyError(f"Ruleset {version} not found.")
    raw = _load_json(path)
    if raw.get("status") == "superseded":
        raise KeyError(f"Ruleset {version} is superseded and not executable.")
    ruleset = Ruleset.model_validate(raw)
    sources = load_sources()
    for spec in ruleset.rules:
        missing = [s for s in spec.source_ids if s not in sources]
        if missing:
            raise ValueError(f"Rule {spec.rule_id} references unknown sources {missing}.")
    return ruleset


def load_ruleset_summary(version: str) -> dict[str, object]:
    """Load raw metadata for any ruleset (including superseded ones)."""
    path = _DATA_DIR / "rulesets" / f"{version}.json"
    if not path.is_file():
        raise KeyError(f"Ruleset {version} not found.")
    return _load_json(path)
