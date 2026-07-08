"""
backend/app/rules/base_rule.py

Abstract base class for all regulatory rules.

Every rule in the system is a subclass of BaseRule. Rules are pure functions:
given the same CompanyData, they always return the same RuleResult.
Rules have no side effects, no shared mutable state, and no I/O.

This module MUST NOT import from:
  - app.parser, app.api, app.services

Import constraint compliance:
  - Imports only from app.models (models layer)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from app.models.company_data import CompanyData
from app.models.enums import RuleCategory, Verdict
from app.models.rule_result import RuleMetadata, RuleResult
from app.models.source_citation import SourceCitation


class BaseRule(ABC):
    """Abstract base class that all regulatory rules must implement.

    Every concrete rule subclass must provide:
      - rule_id: A unique string identifier (e.g., "NTA_3CR")
      - metadata: A RuleMetadata instance citing the regulation
      - evaluate(): A pure function mapping CompanyData → RuleResult

    Rules are stateless. The same instance can be reused across multiple
    evaluations without any cleanup. All state is passed in via CompanyData
    and returned via RuleResult.

    Example:
        >>> class MyRule(BaseRule):
        ...     @property
        ...     def rule_id(self) -> str:
        ...         return "MY_RULE"
        ...
        ...     @property
        ...     def metadata(self) -> RuleMetadata:
        ...         return RuleMetadata(...)
        ...
        ...     def evaluate(self, company: CompanyData) -> RuleResult:
        ...         return self._build_result(
        ...             verdict=Verdict.PASS,
        ...             actual_value="Passed",
        ...             explanation="All conditions met.",
        ...         )
    """

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique identifier for this rule.

        Must be a stable, uppercase snake_case string that matches the
        IDs listed in ARCHITECTURE.md §8.4 and §8.5.

        Returns:
            The unique rule identifier, e.g., "AVG_OPERATING_PROFIT_15CR".
        """

    @property
    @abstractmethod
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for this rule.

        Returns a RuleMetadata instance that cites the exact regulation,
        section, and clause being evaluated.

        Returns:
            The RuleMetadata for this rule.
        """

    @abstractmethod
    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate this rule against the provided CompanyData.

        This method is a pure function: same input always produces same
        output. It must have no side effects and must not modify any state.

        Args:
            company: The canonical company schema. The only input.

        Returns:
            A RuleResult with a PASS, FAIL, or INCONCLUSIVE verdict,
            regulation reference, actual values, gap (if applicable),
            and explanation.
        """

    def _build_result(
        self,
        verdict: Verdict,
        actual_value: str | None = None,
        gap: str | None = None,
        source_citation: SourceCitation | None = None,
        explanation: str = "",
    ) -> RuleResult:
        """Construct a RuleResult from this rule's metadata and the provided values.

        Helper method for consistent RuleResult construction. All concrete
        rule implementations should use this method rather than constructing
        RuleResult directly — it ensures rule_id, category, regulation_reference,
        description, and required_value are always populated from metadata.

        Args:
            verdict: The evaluation outcome: PASS, FAIL, or INCONCLUSIVE.
            actual_value: The company's actual value for this check, formatted
                for human reading (e.g., "₹12.4 Cr"). None if unavailable.
            gap: Quantified shortfall if FAIL, e.g., "₹2.6 Cr below threshold".
                None if the rule passed or no quantifiable gap exists.
            source_citation: Evidence provenance from the Evidence Mapper.
                None at rule evaluation time (attached later by EvidenceMapper).
            explanation: Full human-readable reasoning for the verdict.
                Should explain why the verdict was reached.

        Returns:
            A fully constructed, immutable RuleResult.
        """
        meta = self.metadata
        regulation_reference = meta.section
        if meta.clause:
            regulation_reference = f"{meta.regulation} {meta.section} {meta.clause}"
        else:
            regulation_reference = f"{meta.regulation} {meta.section}"

        return RuleResult(
            rule_id=self.rule_id,
            verdict=verdict,
            category=meta.category,
            regulation_reference=regulation_reference,
            description=meta.description,
            required_value=self._required_value,
            actual_value=actual_value,
            gap=gap,
            source_citation=source_citation,
            explanation=explanation,
            evaluated_at=datetime.now(tz=UTC),
        )

    @property
    def _required_value(self) -> str:
        """Human-readable required threshold for this rule.

        Subclasses should override this to provide a descriptive string,
        e.g., "≥ ₹15 Cr average operating profit across best 3 of 5 FYs".

        Returns:
            A human-readable description of what the rule requires.
        """
        return self.metadata.description

    def _build_inconclusive(
        self,
        reason: str,
        actual_value: str | None = None,
    ) -> RuleResult:
        """Build an INCONCLUSIVE result for missing or low-confidence data.

        Args:
            reason: Why the data is insufficient (displayed in explanation).
            actual_value: What data was available, if any.

        Returns:
            A RuleResult with verdict=INCONCLUSIVE.
        """
        return self._build_result(
            verdict=Verdict.INCONCLUSIVE,
            actual_value=actual_value,
            explanation=(
                f"Cannot determine compliance: {reason}. "
                "Manual review of source documents is required."
            ),
        )

    @property
    def category(self) -> RuleCategory:
        """Convenience accessor for the rule category.

        Returns:
            The RuleCategory (MANDATORY or ADVISORY) from metadata.
        """
        return self.metadata.category
