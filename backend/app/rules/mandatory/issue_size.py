"""
backend/app/rules/mandatory/issue_size.py

EXCHANGE_MIN_ISSUE_SIZE — stock-exchange main-board minimum issue size of
₹10 crore (threshold UNVERIFIED; see sources register).

Ruleset 1.0.0 contained ISSUE_SIZE_5X (issue size ≤ 5× pre-issue net worth,
cited as "ICDR Reg 26(2)"). That condition comes from ICDR 2009 and does not
appear in ICDR 2018; it was removed in ruleset 2.0.0.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.company_data import CompanyData
from app.models.extracted_value import ExtractedValue
from app.rules.mandatory.minimum_capital import _ThresholdRule


class IssueSizeRule(_ThresholdRule):
    """Issue size >= exchange minimum."""

    rule_id = "EXCHANGE_MIN_ISSUE_SIZE"
    _param = "min_issue_size_crore"
    _path = "issue_details.issue_size"
    _label = "Issue size"
    _remediation = (
        "Increase the issue size or consider the SME route (not evaluated by this engine)."
    )

    def _value(self, company: CompanyData) -> ExtractedValue[Decimal] | None:
        return company.issue_details.issue_size
