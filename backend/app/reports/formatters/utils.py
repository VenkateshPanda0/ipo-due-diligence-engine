"""
backend/app/reports/formatters/utils.py

Formatting helpers for deterministic report renderers.

This module MUST NOT import from:
  - app.rules
  - app.intelligence
  - app.api
  - app.services
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.models.enums import IPOStatus, ScreeningOutcome, Verdict


def format_currency(value: Decimal) -> str:
    """Format a Decimal crore value as Indian rupee crores."""
    return f"Rs. {value:,.2f} Cr"


def format_percentage(value: Decimal) -> str:
    """Format a Decimal percentage with two decimal places."""
    return f"{value:.2f}%"


def format_verdict(verdict: Verdict) -> str:
    """Format a rule verdict for text/HTML reports."""
    labels = {
        Verdict.PASS: "[PASS]",
        Verdict.FAIL: "[FAIL]",
        Verdict.INCONCLUSIVE: "[INSUFFICIENT EVIDENCE]",
        Verdict.REQUIRES_HUMAN_REVIEW: "[HUMAN REVIEW]",
        Verdict.NOT_APPLICABLE: "[N/A]",
    }
    return labels[verdict]


_OUTCOME_LABELS = {
    ScreeningOutcome.NO_FAILURE_IDENTIFIED: (
        "No failure identified within supported screening scope"
    ),
    ScreeningOutcome.SCREENING_FAILURE: "Preliminary screening failure under implemented rules",
    ScreeningOutcome.AWAITING_HUMAN_REVIEW: "Awaiting human review",
    ScreeningOutcome.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    ScreeningOutcome.UNSUPPORTED_SCOPE: "Unsupported regulatory scope",
}


def format_outcome(outcome: ScreeningOutcome | None) -> str:
    """Careful product wording for a case outcome."""
    if outcome is None:
        return "Legacy report (no outcome recorded)"
    return _OUTCOME_LABELS[outcome]


def format_status(status: IPOStatus) -> str:
    """Format IPO status for display."""
    return status.value.replace("_", " ").title()


def format_date(value: datetime) -> str:
    """Format a timestamp as ISO 8601 with seconds precision."""
    return value.isoformat(timespec="seconds")
