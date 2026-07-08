"""
backend/app/engine/rules_engine.py

Rules Engine orchestrator — M3-019.

The RulesEngine iterates all registered rules from the RuleRegistry and
collects their results. It enforces rule isolation: each rule's evaluate()
call is independent, and an exception in one rule does not crash others.

ARCHITECTURAL CONSTRAINTS:
  - May import from: models/, rules/ (registry + base_rule only)
  - MUST NOT import from: parser/, api/, services/
  - Rules Engine NEVER contains business logic — that lives in individual rules.
  - CompanyData is the ONLY accepted input.

Design decisions:
  - A failed rule execution (programming error, not a domain FAIL) produces
    an INCONCLUSIVE result with an explanation describing the internal error.
    This preserves the contract that evaluate_all() always returns a result
    per rule, even under unexpected conditions.
  - Results are ordered deterministically: same order as the registry.
"""

from __future__ import annotations

import traceback
from datetime import UTC, datetime

from app.models.company_data import CompanyData
from app.models.enums import RuleCategory, Verdict
from app.models.rule_result import RuleResult
from app.rules.registry import RuleRegistry

# Fallback metadata used when a rule raises an unexpected exception
_FALLBACK_METADATA_DATE = datetime(2018, 11, 1).date()


class RulesEngine:
    """Orchestrates rule evaluation against CompanyData.

    The RulesEngine is the execution framework for all regulatory checks.
    It does not contain any regulatory knowledge itself — that lives in
    individual BaseRule subclasses. The engine's sole responsibilities are:

      1. Load rules from the registry.
      2. Execute each rule's evaluate() method against CompanyData.
      3. Collect results into an ordered list.
      4. Isolate rule failures so one broken rule cannot abort the evaluation.

    The engine is stateless: a single instance can be reused across multiple
    company evaluations without any cleanup.

    Example::

        engine = RulesEngine(RuleRegistry())
        results = engine.evaluate_all(company)
        assert len(results) == 16  # 11 mandatory + 5 advisory
    """

    def __init__(self, registry: RuleRegistry) -> None:
        """Initialise the engine with a pre-built rule registry.

        Args:
            registry: A fully initialised RuleRegistry instance. The engine
                holds a reference to the registry; it does not copy it.
        """
        self._registry = registry

    def evaluate_all(self, company: CompanyData) -> list[RuleResult]:
        """Evaluate every registered rule against the provided CompanyData.

        Iterates all rules in registry order (mandatory first, then advisory)
        and calls evaluate() on each. If a rule raises an unexpected exception
        (programming error), the exception is caught and that rule's result is
        set to INCONCLUSIVE with an error explanation. All other rules continue
        to execute normally.

        Args:
            company: The canonical company schema. Passed unchanged to each
                rule's evaluate() method.

        Returns:
            An ordered list of RuleResult objects, one per registered rule.
            The order is deterministic and matches the registry registration order.
        """
        results: list[RuleResult] = []

        for rule in self._registry.get_all_rules():
            try:
                result = rule.evaluate(company)
            except Exception as exc:  # noqa: BLE001
                # A programming error in a rule must not crash the entire
                # evaluation. Produce an INCONCLUSIVE result so the report
                # can still be generated with the other rules' verdicts.
                tb_summary = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                )
                result = RuleResult(
                    rule_id=rule.rule_id,
                    verdict=Verdict.INCONCLUSIVE,
                    category=rule.category,
                    regulation_reference=rule.metadata.section,
                    description=rule.metadata.description,
                    required_value=rule._required_value,
                    actual_value=None,
                    gap=None,
                    source_citation=None,
                    explanation=(
                        f"Rule evaluation failed due to an internal error: "
                        f"{type(exc).__name__}: {exc}. "
                        "Manual review is required. "
                        f"Traceback summary: {tb_summary[:500]}"
                    ),
                    evaluated_at=datetime.now(tz=UTC),
                )
            results.append(result)

        return results

    def evaluate_mandatory(self, company: CompanyData) -> list[RuleResult]:
        """Evaluate only mandatory rules against the provided CompanyData.

        Convenience method that filters to mandatory rules only, following
        the same isolation semantics as evaluate_all().

        Args:
            company: The canonical company schema.

        Returns:
            An ordered list of RuleResult objects for mandatory rules only.
        """
        results: list[RuleResult] = []

        for rule in self._registry.get_mandatory_rules():
            try:
                result = rule.evaluate(company)
            except Exception as exc:  # noqa: BLE001
                result = RuleResult(
                    rule_id=rule.rule_id,
                    verdict=Verdict.INCONCLUSIVE,
                    category=RuleCategory.MANDATORY,
                    regulation_reference=rule.metadata.section,
                    description=rule.metadata.description,
                    required_value=rule._required_value,
                    actual_value=None,
                    gap=None,
                    source_citation=None,
                    explanation=(
                        f"Rule evaluation failed due to an internal error: "
                        f"{type(exc).__name__}: {exc}."
                    ),
                    evaluated_at=datetime.now(tz=UTC),
                )
            results.append(result)

        return results

    def evaluate_advisory(self, company: CompanyData) -> list[RuleResult]:
        """Evaluate only advisory rules against the provided CompanyData.

        Convenience method that filters to advisory rules only.

        Args:
            company: The canonical company schema.

        Returns:
            An ordered list of RuleResult objects for advisory rules only.
        """
        results: list[RuleResult] = []

        for rule in self._registry.get_advisory_rules():
            try:
                result = rule.evaluate(company)
            except Exception as exc:  # noqa: BLE001
                result = RuleResult(
                    rule_id=rule.rule_id,
                    verdict=Verdict.INCONCLUSIVE,
                    category=RuleCategory.ADVISORY,
                    regulation_reference=rule.metadata.section,
                    description=rule.metadata.description,
                    required_value=rule._required_value,
                    actual_value=None,
                    gap=None,
                    source_citation=None,
                    explanation=(
                        f"Rule evaluation failed due to an internal error: "
                        f"{type(exc).__name__}: {exc}."
                    ),
                    evaluated_at=datetime.now(tz=UTC),
                )
            results.append(result)

        return results
