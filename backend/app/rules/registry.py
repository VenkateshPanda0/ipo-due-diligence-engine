"""
backend/app/rules/registry.py

Rule registry: binds executable rule classes to the specs of one ruleset version.

Every rule in the ruleset JSON must have exactly one implementation and vice
versa; a mismatch raises at start-up so a ruleset can never silently drop or
add a rule.
"""

from __future__ import annotations

from app.models.enums import RuleCategory
from app.regulatory.registry import CURRENT_RULESET_VERSION, Ruleset, load_ruleset
from app.rules.advisory.auditor import AuditorQualificationRule
from app.rules.advisory.governance import AuditCommitteeRule, BoardIndependenceRule
from app.rules.advisory.litigation import LitigationRiskRule
from app.rules.advisory.rpt import RPTDisclosureRule
from app.rules.base_rule import BaseRule
from app.rules.mandatory.eligibility import IneligibleEntitiesRule, NameChangeRule, QIBRouteRule
from app.rules.mandatory.float_requirements import FloatRequirementsRule
from app.rules.mandatory.issue_size import IssueSizeRule
from app.rules.mandatory.minimum_capital import MinMarketCapRule, MinPostIssueCapitalRule
from app.rules.mandatory.net_tangible_assets import MonetaryAssetsRule, NTARule
from app.rules.mandatory.net_worth import NetWorthRule
from app.rules.mandatory.profitability import ProfitabilityRule
from app.rules.mandatory.promoter import PromoterContributionRule, PromoterLockInRule
from app.rules.mandatory.track_record import TrackRecordRule

RULE_CLASSES: tuple[type[BaseRule], ...] = (
    IneligibleEntitiesRule,
    NTARule,
    MonetaryAssetsRule,
    ProfitabilityRule,
    NetWorthRule,
    NameChangeRule,
    QIBRouteRule,
    PromoterContributionRule,
    PromoterLockInRule,
    FloatRequirementsRule,
    MinPostIssueCapitalRule,
    MinMarketCapRule,
    IssueSizeRule,
    TrackRecordRule,
    BoardIndependenceRule,
    AuditCommitteeRule,
    RPTDisclosureRule,
    AuditorQualificationRule,
    LitigationRiskRule,
)


class RuleRegistry:
    """Registry of rule instances for one ruleset version."""

    def __init__(self, version: str = CURRENT_RULESET_VERSION) -> None:
        self._ruleset = load_ruleset(version)
        classes = {cls.rule_id: cls for cls in RULE_CLASSES}
        spec_ids = [spec.rule_id for spec in self._ruleset.rules]
        missing_impl = sorted(set(spec_ids) - set(classes))
        if missing_impl:
            raise ValueError(f"Ruleset {version} has rules without implementation: {missing_impl}")
        unused = sorted(set(classes) - set(spec_ids))
        if unused:
            raise ValueError(f"Implemented rules missing from ruleset {version}: {unused}")
        if len(set(spec_ids)) != len(spec_ids):
            raise ValueError(f"Duplicate rule_id in ruleset {version}.")
        self._rules: dict[str, BaseRule] = {
            spec.rule_id: classes[spec.rule_id](spec) for spec in self._ruleset.rules
        }

    @property
    def ruleset(self) -> Ruleset:
        """The ruleset these rules were bound to."""
        return self._ruleset

    @property
    def version(self) -> str:
        """Ruleset version string."""
        return self._ruleset.version

    def get_all_rules(self) -> list[BaseRule]:
        """All rules in ruleset order."""
        return list(self._rules.values())

    def get_mandatory_rules(self) -> list[BaseRule]:
        """Rules that feed the case outcome."""
        return [r for r in self._rules.values() if r.category == RuleCategory.MANDATORY]

    def get_advisory_rules(self) -> list[BaseRule]:
        """Rules that never affect the case outcome."""
        return [r for r in self._rules.values() if r.category == RuleCategory.ADVISORY]

    def get_rule(self, rule_id: str) -> BaseRule:
        """Return a rule by ID."""
        try:
            return self._rules[rule_id]
        except KeyError:
            raise KeyError(
                f"Rule '{rule_id}' is not registered. Available rule IDs: {sorted(self._rules)}"
            ) from None

    def get_rule_ids(self) -> list[str]:
        """All rule IDs in ruleset order."""
        return list(self._rules)

    def __len__(self) -> int:
        return len(self._rules)

    def __contains__(self, rule_id: object) -> bool:
        return rule_id in self._rules
