"""
backend/app/reports/formatters/utils.py

Formatting helpers for deterministic report renderers.

This module MUST NOT import from:
  - app.rules
  - app.parser
  - app.api
  - app.services
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.models.enums import IPOStatus, Verdict


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
        Verdict.INCONCLUSIVE: "[REVIEW]",
    }
    return labels[verdict]


def format_status(status: IPOStatus) -> str:
    """Format IPO status for display."""
    return status.value.replace("_", " ").title()


def format_date(value: datetime) -> str:
    """Format a timestamp as ISO 8601 with seconds precision."""
    return value.isoformat(timespec="seconds")
