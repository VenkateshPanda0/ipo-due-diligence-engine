"""
backend/app/rules/registry.py

Rule Registry with auto-discovery of all BaseRule subclasses.

The RuleRegistry discovers all concrete rule implementations from the
mandatory/ and advisory/ packages. It is immutable after initialization —
rules are loaded once and cached. The registry provides filtered views
by category and direct lookup by rule_id.

ARCHITECTURAL CONSTRAINTS:
  - Registry discovers rules by importing known modules — no filesystem scanning.
  - Registry is the only place in the codebase that knows which rule classes exist.
  - Engine and services use the registry; they do not import rule classes directly.

Import constraints:
  - MUST NOT import from: app.parser, app.api, app.services
  - Imports from: app.models, app.rules.base_rule, and all rule modules
"""

from __future__ import annotations

from typing import Final

from app.models.enums import RuleCategory
from app.rules.advisory.auditor import AuditorQualificationRule
from app.rules.advisory.governance import AuditCommitteeRule, BoardIndependenceRule
from app.rules.advisory.litigation import LitigationRiskRule
from app.rules.advisory.rpt import RPTDisclosureRule
from app.rules.base_rule import BaseRule
from app.rules.mandatory.float_requirements import FloatRequirementsRule
from app.rules.mandatory.issue_size import IssueSizeRule
from app.rules.mandatory.minimum_capital import MinMarketCapRule, MinPostIssueCapitalRule
from app.rules.mandatory.net_tangible_assets import MonetaryAssetsRule, NTARule
from app.rules.mandatory.net_worth import NetWorthRule
from app.rules.mandatory.profitability import ProfitabilityRule
from app.rules.mandatory.promoter import PromoterContributionRule, PromoterLockInRule
from app.rules.mandatory.track_record import TrackRecordRule


class RuleRegistry:
    """Immutable registry of all registered regulatory rules.

    Discovers and instantiates all concrete BaseRule implementations at
    initialization time. After construction, the registry is immutable —
    rules cannot be added, removed, or modified.

    The registry is the single authoritative source of which rules exist
    in the system. The RulesEngine and other consumers retrieve rules
    exclusively through the registry API.

    Example:
        >>> registry = RuleRegistry()
        >>> rules = registry.get_all_rules()
        >>> len(rules)
        16
        >>> mandatory = registry.get_mandatory_rules()
        >>> len(mandatory)
        11
        >>> rule = registry.get_rule("NTA_3CR")
        >>> rule.rule_id
        'NTA_3CR'
    """

    def __init__(self) -> None:
        """Initialize the registry and discover all rules.

        Rules are instantiated in a deterministic order: mandatory rules
        first (in the order they appear in ARCHITECTURE.md §8.4), then
        advisory rules (in the order they appear in §8.5).
        """
        self._rules: Final[dict[str, BaseRule]] = self._build_rule_map()

    @staticmethod
    def _build_rule_map() -> dict[str, BaseRule]:
        """Instantiate all rules and index them by rule_id.

        Returns:
            An ordered dict of rule_id → BaseRule instance. Mandatory rules
            appear first, followed by advisory rules.

        Raises:
            ValueError: If two rules share the same rule_id (programming error).
        """
        # Instantiate rules in deterministic order matching ARCHITECTURE.md §8.4 and §8.5
        instances: list[BaseRule] = [
            # Mandatory rules — 11 total
            NTARule(),
            MonetaryAssetsRule(),
            ProfitabilityRule(),
            NetWorthRule(),
            IssueSizeRule(),
            TrackRecordRule(),
            FloatRequirementsRule(),
            PromoterContributionRule(),
            PromoterLockInRule(),
            MinPostIssueCapitalRule(),
            MinMarketCapRule(),
            # Advisory rules — 5 total
            BoardIndependenceRule(),
            AuditCommitteeRule(),
            RPTDisclosureRule(),
            AuditorQualificationRule(),
            LitigationRiskRule(),
        ]

        rule_map: dict[str, BaseRule] = {}
        for rule in instances:
            if rule.rule_id in rule_map:
                raise ValueError(
                    f"Duplicate rule_id detected: '{rule.rule_id}'. "
                    "Each rule must have a unique rule_id."
                )
            rule_map[rule.rule_id] = rule

        return rule_map

    def get_all_rules(self) -> list[BaseRule]:
        """Return all registered rules in deterministic order.

        Mandatory rules are returned first, followed by advisory rules.

        Returns:
            Ordered list of all registered BaseRule instances.
        """
        return list(self._rules.values())

    def get_mandatory_rules(self) -> list[BaseRule]:
        """Return all mandatory rules.

        Returns:
            List of BaseRule instances with category == RuleCategory.MANDATORY.
        """
        return [r for r in self._rules.values() if r.category == RuleCategory.MANDATORY]

    def get_advisory_rules(self) -> list[BaseRule]:
        """Return all advisory rules.

        Returns:
            List of BaseRule instances with category == RuleCategory.ADVISORY.
        """
        return [r for r in self._rules.values() if r.category == RuleCategory.ADVISORY]

    def get_rule(self, rule_id: str) -> BaseRule:
        """Retrieve a rule by its unique identifier.

        Args:
            rule_id: The unique rule identifier, e.g., "NTA_3CR".

        Returns:
            The BaseRule instance for the given rule_id.

        Raises:
            KeyError: If no rule with the given rule_id is registered.
        """
        try:
            return self._rules[rule_id]
        except KeyError:
            available = sorted(self._rules.keys())
            raise KeyError(
                f"Rule '{rule_id}' is not registered. "
                f"Available rule IDs: {available}"
            ) from None

    def get_rule_ids(self) -> list[str]:
        """Return all registered rule IDs in order.

        Returns:
            List of rule ID strings in registration order.
        """
        return list(self._rules.keys())

    def __len__(self) -> int:
        """Return the total number of registered rules."""
        return len(self._rules)

    def __contains__(self, rule_id: object) -> bool:
        """Check if a rule_id is registered.

        Args:
            rule_id: The rule identifier to check.

        Returns:
            True if a rule with this rule_id exists in the registry.
        """
        return rule_id in self._rules
