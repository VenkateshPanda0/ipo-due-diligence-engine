"""
backend/app/engine/rules_engine.py

Runs every rule of a registry against one CompanyData snapshot.

A programming error inside one rule must not crash the evaluation or leak
internals into the report: the error is logged server-side and that rule is
reported as REQUIRES_HUMAN_REVIEW with a generic explanation.

ARCHITECTURAL CONSTRAINTS: may import from models/, rules/; not parser/api/services.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.models.company_data import CompanyData
from app.models.enums import Verdict
from app.models.rule_result import RuleResult
from app.rules.base_rule import BaseRule
from app.rules.registry import RuleRegistry

logger = logging.getLogger(__name__)


class RulesEngine:
    """Evaluate all registered rules in ruleset order."""

    def __init__(self, registry: RuleRegistry) -> None:
        self._registry = registry

    def evaluate_all(self, company: CompanyData) -> list[RuleResult]:
        """Evaluate every rule; one result per rule, in ruleset order."""
        return [self._safe_evaluate(rule, company) for rule in self._registry.get_all_rules()]

    def evaluate_mandatory(self, company: CompanyData) -> list[RuleResult]:
        """Evaluate mandatory rules only."""
        return [self._safe_evaluate(r, company) for r in self._registry.get_mandatory_rules()]

    def evaluate_advisory(self, company: CompanyData) -> list[RuleResult]:
        """Evaluate advisory rules only."""
        return [self._safe_evaluate(r, company) for r in self._registry.get_advisory_rules()]

    @staticmethod
    def _safe_evaluate(rule: BaseRule, company: CompanyData) -> RuleResult:
        try:
            return rule.evaluate(company)
        except Exception:
            logger.exception("rule_evaluation_error", extra={"rule_id": rule.rule_id})
            spec = rule.spec
            return RuleResult(
                rule_id=rule.rule_id,
                verdict=Verdict.REQUIRES_HUMAN_REVIEW,
                category=rule.category,
                regulation_reference=f"{spec.instrument}, {spec.provision}",
                description=spec.name,
                required_value=rule.required_value,
                explanation=(
                    "This rule could not be evaluated because of an internal error. "
                    "The error has been logged; manual assessment is required."
                ),
                evaluated_at=datetime.now(tz=UTC),
                rule_name=spec.name,
                rule_version=spec.rule_version,
                legal_category=spec.legal_category,
                verification_status=spec.verification_status,
                source_url=spec.source_url,
                requires_human_review=True,
                review_reasons=["internal evaluation error"],
                limitations=list(spec.limitations),
            )
