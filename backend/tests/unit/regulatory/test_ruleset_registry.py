"""Integrity tests for the regulatory source register and versioned rulesets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.enums import RuleCategory, VerificationStatus
from app.regulatory.registry import (
    CURRENT_RULESET_VERSION,
    available_ruleset_versions,
    load_ruleset,
    load_ruleset_summary,
    load_sources,
)
from app.rules.registry import RULE_CLASSES, RuleRegistry

DATA = Path(__file__).resolve().parents[3] / "app" / "regulatory" / "data"


def test_current_ruleset_loads() -> None:
    rs = load_ruleset()
    assert rs.version == CURRENT_RULESET_VERSION == "2.0.0"
    assert rs.status == "active"
    assert not rs.legal_review.confirmed


def test_every_rule_has_resolvable_sources_and_status() -> None:
    sources = load_sources()
    for spec in load_ruleset().rules:
        assert spec.source_ids, spec.rule_id
        assert all(s in sources for s in spec.source_ids)
        assert spec.verification_status in VerificationStatus
        assert spec.decision_procedure and spec.applicability and spec.required_inputs


def test_no_rule_claims_legal_review() -> None:
    assert all(
        s.verification_status != VerificationStatus.LEGAL_REVIEWED for s in load_ruleset().rules
    )


def test_primary_text_checked_rules_cite_hashed_primary_source() -> None:
    sources = load_sources()
    for spec in load_ruleset().rules:
        if spec.verification_status == VerificationStatus.PRIMARY_TEXT_CHECKED:
            primary = [sources[s] for s in spec.source_ids if sources[s].kind == "primary"]
            assert primary and all(p.document_sha256 for p in primary), spec.rule_id


def test_no_icdr_2009_numbering_in_icdr_rules() -> None:
    for spec in load_ruleset().rules:
        if "ICDR" in spec.instrument:
            for stale in ("Regulation 26", "Regulation 32", "Regulation 36"):
                assert stale not in spec.provision, spec.rule_id


def test_legacy_ruleset_is_superseded_and_not_executable() -> None:
    assert "1.0.0" in available_ruleset_versions()
    assert load_ruleset_summary("1.0.0")["status"] == "superseded"
    with pytest.raises(KeyError):
        load_ruleset("1.0.0")


def test_unknown_ruleset() -> None:
    with pytest.raises(KeyError):
        load_ruleset("9.9.9")


def test_registry_binds_every_spec_to_one_class() -> None:
    reg = RuleRegistry()
    assert len(reg) == len(load_ruleset().rules) == len(RULE_CLASSES)
    assert reg.version == "2.0.0"
    assert len(reg.get_mandatory_rules()) + len(reg.get_advisory_rules()) == len(reg)
    for rule in reg.get_all_rules():
        assert rule.category == rule.spec.category


def test_registry_rejects_unknown_rule() -> None:
    with pytest.raises(KeyError):
        RuleRegistry().get_rule("NOPE")


def test_parameters_are_numeric() -> None:
    for spec in load_ruleset().rules:
        for name in spec.parameters:
            spec.decimal(name)


def test_ruleset_files_are_valid_json_with_unique_ids() -> None:
    for path in (DATA / "rulesets").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        ids = [r["rule_id"] for r in data["rules"]]
        assert len(ids) == len(set(ids)), path.name


def test_advisory_rules_include_heuristics_only_as_advisory() -> None:
    for spec in load_ruleset().rules:
        if spec.legal_category.value == "diligence_indicator":
            assert spec.category == RuleCategory.ADVISORY
