"""
backend/app/models/rule_result.py

RuleResult and RuleMetadata — the outputs of the Rules Engine.

RuleMetadata describes a rule's regulatory basis (regulation, section,
clause). RuleResult carries the verdict, evidence, and explanation for
a single rule evaluation. Both are immutable after construction.

This module MUST NOT import from:
  - app.rules, app.parser, app.api, app.engine, app.services

RuleResult objects flow from the Rules Engine → Decision Engine →
Evidence Mapper → IPOReport. Nothing downstream may mutate them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RuleCategory, Verdict
from app.models.source_citation import SourceCitation


class RuleMetadata(BaseModel):
    """Regulatory citation and classification for a rule.

    Every BaseRule implementation carries one RuleMetadata instance that
    records the exact regulation being evaluated. This data appears in the
    IPOReport's Rule Explorer section.

    Attributes:
        regulation: Full name of the regulation, e.g.,
            "SEBI (ICDR) Regulations, 2018".
        section: Section or regulation number, e.g., "Regulation 26(1)".
        clause: Specific sub-clause, e.g., "Clause (a)", if applicable.
        description: Plain-English description of what the rule checks.
        category: Whether this is a MANDATORY or ADVISORY rule.
        effective_date: Date when this version of the regulation took effect.
        source_url: Link to the SEBI gazette or regulatory source, if known.

    Example:
        >>> from datetime import date
        >>> from app.models.enums import RuleCategory
        >>> metadata = RuleMetadata(
        ...     regulation="SEBI (ICDR) Regulations, 2018",
        ...     section="Regulation 26(1)",
        ...     clause="Clause (b)",
        ...     description="Average operating profit ≥ ₹15 Cr across 3 of 5 FYs",
        ...     category=RuleCategory.MANDATORY,
        ...     effective_date=date(2018, 11, 1),
        ...     source_url="https://www.sebi.gov.in/legal/regulations/nov-2018/sebi-icdr-2018",
        ... )
        >>> metadata.category
        <RuleCategory.MANDATORY: 'mandatory'>
    """

    model_config = ConfigDict(frozen=True)

    regulation: str
    section: str
    clause: str | None = None
    description: str
    category: RuleCategory
    effective_date: date
    source_url: str | None = None


class RuleResult(BaseModel):
    """Verdict and evidence for a single rule evaluation.

    Produced by BaseRule.evaluate(). Immutable after construction.
    Flows through the system from Rules Engine to IPOReport without
    modification — the Evidence Mapper annotates rather than mutates.

    The evaluated_at timestamp records when the rule was evaluated.
    It is included for audit trail purposes but does not affect
    reproducibility — the same CompanyData always produces the same
    verdict regardless of when evaluation occurred.

    Attributes:
        rule_id: Unique string identifier matching the rule's rule_id property,
            e.g., "AVG_OPERATING_PROFIT_15CR".
        verdict: PASS, FAIL, or INCONCLUSIVE.
        category: MANDATORY or ADVISORY.
        regulation_reference: Compact citation, e.g., "SEBI ICDR Reg. 26(1)(b)".
        description: Human-readable description of what was checked.
        required_value: What the regulation requires, e.g., "≥ ₹15 Cr average".
        actual_value: What the company had, e.g., "₹12.4 Cr average (FY22–24)".
            None if the data was not available.
        gap: Quantified shortfall, e.g., "₹2.6 Cr below threshold". None if
            the rule passed or no quantifiable gap exists.
        source_citation: Evidence provenance — attached by the Evidence Mapper.
            None until the Evidence Mapper processes the result.
        explanation: Full human-readable reasoning for the verdict.
        evaluated_at: UTC timestamp of evaluation.

    Example:
        >>> from datetime import datetime, timezone
        >>> from app.models.enums import RuleCategory, Verdict
        >>> result = RuleResult(
        ...     rule_id="AVG_OPERATING_PROFIT_15CR",
        ...     verdict=Verdict.FAIL,
        ...     category=RuleCategory.MANDATORY,
        ...     regulation_reference="SEBI ICDR Reg. 26(1)(b)",
        ...     description="Average operating profit ≥ ₹15 Cr",
        ...     required_value="≥ ₹15 Cr (average across best 3 of 5 FYs)",
        ...     actual_value="₹12.4 Cr",
        ...     gap="₹2.6 Cr below threshold",
        ...     explanation="Average operating profit of ₹12.4 Cr is below "
        ...                 "the ₹15 Cr threshold required by ICDR Reg. 26(1)(b).",
        ... )
        >>> result.verdict
        <Verdict.FAIL: 'fail'>
    """

    model_config = ConfigDict(frozen=True)

    rule_id: str
    verdict: Verdict
    category: RuleCategory
    regulation_reference: str
    description: str
    required_value: str
    actual_value: str | None = None
    gap: str | None = None
    source_citation: SourceCitation | None = None
    explanation: str
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC)
    )
