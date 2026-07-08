"""
backend/app/rules/mandatory/track_record.py

Mandatory Rule: Operating Track Record ≥ 3 Full Fiscal Years.

Implements SEBI (ICDR) Regulations, 2018, Regulation 26(1), which requires
a company seeking a mainboard IPO to have at least three full years of
operating history. This rule ensures that only companies with an established
operating track record can access the public markets.

This module MUST NOT import from:
  - app.parser, app.api, app.services, app.engine

Import constraint compliance:
  - Imports only from app.models and app.rules.base_rule
"""

from __future__ import annotations

from datetime import date

from app.models.company_data import CompanyData
from app.models.enums import RuleCategory, Verdict
from app.models.rule_result import RuleMetadata, RuleResult
from app.rules.base_rule import BaseRule

_SEBI_ICDR_REGULATION = "SEBI (ICDR) Regulations, 2018"
_SEBI_ICDR_SOURCE_URL = "https://www.sebi.gov.in/legal/regulations/nov-2018/sebi-icdr-2018.html"
_MIN_YEARS_OF_OPERATION = 3


class TrackRecordRule(BaseRule):
    """Mandatory Rule — TRACK_RECORD_3Y.

    Enforces that the company has been in operation for at least three full
    fiscal years, as required by SEBI (ICDR) Regulations, 2018, Regulation 26(1).

    The check uses ``company.financials.years_of_operation``, which is a plain
    ``int`` field representing the total number of complete fiscal years the
    company has been operational. Because this is a scalar (not an
    ``ExtractedValue``), no reliability check is performed — the value is
    always considered authoritative.

    Evaluation logic:
      - PASS if ``years_of_operation ≥ 3``.
      - FAIL if ``years_of_operation < 3``.

    Data source:
      - ``company.financials.years_of_operation`` — plain ``int``

    Example::

        >>> rule = TrackRecordRule()
        >>> rule.rule_id
        'TRACK_RECORD_3Y'
        >>> rule.category.value
        'mandatory'
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for the Track Record rule.

        Returns:
            The string ``"TRACK_RECORD_3Y"``.
        """
        return "TRACK_RECORD_3Y"

    @property
    def metadata(self) -> RuleMetadata:
        """Regulatory metadata for SEBI ICDR Regulation 26(1).

        Returns:
            A frozen RuleMetadata instance citing the exact regulation and
            section that mandates the minimum operating track record.
        """
        return RuleMetadata(
            regulation=_SEBI_ICDR_REGULATION,
            section="Regulation 26(1)",
            clause=None,
            description=(
                "Company must have at least 3 full fiscal years of operating history"
            ),
            category=RuleCategory.MANDATORY,
            effective_date=date(2018, 11, 1),
            source_url=_SEBI_ICDR_SOURCE_URL,
        )

    @property
    def _required_value(self) -> str:
        """Human-readable statement of the required threshold.

        Returns:
            The string ``"≥ 3 full years of operating history"``.
        """
        return "≥ 3 full years of operating history"

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate the operating track record against CompanyData.

        Checks that the company has been operating for at least three full
        fiscal years. The check is deterministic — ``years_of_operation`` is
        a plain integer with no provenance metadata to validate.

        Args:
            company: The canonical CompanyData object containing financial history.

        Returns:
            A RuleResult with:
              - ``PASS`` if ``years_of_operation ≥ 3``.
              - ``FAIL`` if ``years_of_operation < 3``, with a gap message
                indicating how many additional years are required.
        """
        years: int = company.financials.years_of_operation
        actual_value = f"{years} year{'s' if years != 1 else ''} of operation"

        if years >= _MIN_YEARS_OF_OPERATION:
            return self._build_result(
                verdict=Verdict.PASS,
                actual_value=actual_value,
                gap=None,
                explanation=(
                    f"Company has {years} years of operation, which meets or exceeds "
                    f"the minimum of {_MIN_YEARS_OF_OPERATION} full fiscal years "
                    "required by SEBI (ICDR) Regulations, 2018, Regulation 26(1)."
                ),
            )

        shortfall = _MIN_YEARS_OF_OPERATION - years
        gap = (
            f"Company has {years} year{'s' if years != 1 else ''} of operation; "
            f"requires at least {_MIN_YEARS_OF_OPERATION} full fiscal years"
        )
        return self._build_result(
            verdict=Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=(
                f"Company has only {years} year{'s' if years != 1 else ''} of "
                f"operating history, which is {shortfall} year"
                f"{'s' if shortfall != 1 else ''} short of the minimum "
                f"{_MIN_YEARS_OF_OPERATION} full fiscal years required under "
                "SEBI (ICDR) Regulations, 2018, Regulation 26(1). "
                "The company is not eligible for a mainboard IPO until the "
                "required track record is established."
            ),
        )
