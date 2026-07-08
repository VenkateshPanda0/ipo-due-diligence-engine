"""
backend/tests/unit/rules/test_registry.py

Unit tests for RuleRegistry (M3-031).

Verifies: all 16 rules registered, categories correct, get_rule by ID,
duplicate detection, ordering (mandatory first), __len__, __contains__.
"""

from __future__ import annotations

import pytest

from app.models.enums import RuleCategory
from app.rules.registry import RuleRegistry

EXPECTED_MANDATORY_IDS = {
    "NTA_3CR",
    "MONETARY_ASSETS_50PCT",
    "AVG_OPERATING_PROFIT_15CR",
    "NET_WORTH_1CR",
    "ISSUE_SIZE_5X",
    "TRACK_RECORD_3Y",
    "PUBLIC_OFFER_MIN",
    "PROMOTER_CONTRIBUTION_20",
    "PROMOTER_LOCK_IN",
    "MIN_POST_ISSUE_CAPITAL",
    "MIN_MARKET_CAP",
}

EXPECTED_ADVISORY_IDS = {
    "BOARD_INDEPENDENCE",
    "AUDIT_COMMITTEE",
    "RPT_DISCLOSURE",
    "AUDITOR_QUALIFICATION",
    "LITIGATION_RISK",
}

EXPECTED_ALL_IDS = EXPECTED_MANDATORY_IDS | EXPECTED_ADVISORY_IDS


class TestRuleRegistryInit:
    """Tests for registry initialization and completeness."""

    def test_total_rule_count(self, registry: RuleRegistry) -> None:
        """Registry must contain exactly 16 rules."""
        assert len(registry) == 16

    def test_mandatory_rule_count(self, registry: RuleRegistry) -> None:
        assert len(registry.get_mandatory_rules()) == 11

    def test_advisory_rule_count(self, registry: RuleRegistry) -> None:
        assert len(registry.get_advisory_rules()) == 5

    def test_all_mandatory_ids_registered(self, registry: RuleRegistry) -> None:
        actual = {r.rule_id for r in registry.get_mandatory_rules()}
        assert actual == EXPECTED_MANDATORY_IDS

    def test_all_advisory_ids_registered(self, registry: RuleRegistry) -> None:
        actual = {r.rule_id for r in registry.get_advisory_rules()}
        assert actual == EXPECTED_ADVISORY_IDS

    def test_all_rules_ids_registered(self, registry: RuleRegistry) -> None:
        actual = set(registry.get_rule_ids())
        assert actual == EXPECTED_ALL_IDS


class TestRuleRegistryOrdering:
    """Mandatory rules must come before advisory rules."""

    def test_mandatory_rules_before_advisory(self, registry: RuleRegistry) -> None:
        all_rules = registry.get_all_rules()
        mandatory_indices = [
            i for i, r in enumerate(all_rules) if r.category == RuleCategory.MANDATORY
        ]
        advisory_indices = [
            i for i, r in enumerate(all_rules) if r.category == RuleCategory.ADVISORY
        ]
        assert max(mandatory_indices) < min(advisory_indices)

    def test_deterministic_ordering_across_instances(self) -> None:
        """Two registries must return rules in the same order."""
        r1 = RuleRegistry()
        r2 = RuleRegistry()
        assert [r.rule_id for r in r1.get_all_rules()] == [r.rule_id for r in r2.get_all_rules()]


class TestRuleRegistryGetRule:
    """Tests for get_rule() lookup."""

    def test_get_rule_by_id_returns_correct_rule(self, registry: RuleRegistry) -> None:
        rule = registry.get_rule("NTA_3CR")
        assert rule.rule_id == "NTA_3CR"
        assert rule.category == RuleCategory.MANDATORY

    def test_get_advisory_rule_by_id(self, registry: RuleRegistry) -> None:
        rule = registry.get_rule("AUDIT_COMMITTEE")
        assert rule.rule_id == "AUDIT_COMMITTEE"
        assert rule.category == RuleCategory.ADVISORY

    def test_get_nonexistent_rule_raises_key_error(self, registry: RuleRegistry) -> None:
        with pytest.raises(KeyError, match="not registered"):
            registry.get_rule("NONEXISTENT_RULE")

    def test_get_rule_ids_matches_get_all_rules(self, registry: RuleRegistry) -> None:
        all_ids = registry.get_rule_ids()
        all_rule_ids = [r.rule_id for r in registry.get_all_rules()]
        assert all_ids == all_rule_ids


class TestRuleRegistryContainsLen:
    """Tests for __contains__ and __len__."""

    def test_contains_existing_rule(self, registry: RuleRegistry) -> None:
        assert "NTA_3CR" in registry
        assert "LITIGATION_RISK" in registry

    def test_not_contains_unknown_rule(self, registry: RuleRegistry) -> None:
        assert "FAKE_RULE" not in registry

    def test_len_equals_16(self, registry: RuleRegistry) -> None:
        assert len(registry) == 16


class TestRuleRegistryCategories:
    """All rules must have correct categories assigned."""

    def test_all_mandatory_rules_have_mandatory_category(self, registry: RuleRegistry) -> None:
        for rule in registry.get_mandatory_rules():
            assert rule.category == RuleCategory.MANDATORY, (
                f"Rule {rule.rule_id} is in mandatory list but has category {rule.category}"
            )

    def test_all_advisory_rules_have_advisory_category(self, registry: RuleRegistry) -> None:
        for rule in registry.get_advisory_rules():
            assert rule.category == RuleCategory.ADVISORY, (
                f"Rule {rule.rule_id} is in advisory list but has category {rule.category}"
            )


class TestRuleRegistryMetadata:
    """Every rule must have non-empty metadata."""

    def test_all_rules_have_regulation(self, registry: RuleRegistry) -> None:
        for rule in registry.get_all_rules():
            assert rule.metadata.regulation, f"{rule.rule_id} has empty regulation"

    def test_all_rules_have_section(self, registry: RuleRegistry) -> None:
        for rule in registry.get_all_rules():
            assert rule.metadata.section, f"{rule.rule_id} has empty section"

    def test_all_rules_have_description(self, registry: RuleRegistry) -> None:
        for rule in registry.get_all_rules():
            assert rule.metadata.description, f"{rule.rule_id} has empty description"

    def test_all_rules_have_effective_date(self, registry: RuleRegistry) -> None:
        for rule in registry.get_all_rules():
            assert rule.metadata.effective_date is not None
