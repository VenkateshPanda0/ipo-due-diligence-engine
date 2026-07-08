"""
backend/app/rules/advisory/governance.py

Advisory governance rules: BOARD_INDEPENDENCE and AUDIT_COMMITTEE.

These rules implement the board composition requirements of the Companies Act
2013 and SEBI LODR Regulations 2015. They are advisory (non-blocking) —
failures are flagged as governance risk warnings in the IPOReport.

Import constraints:
  - MUST NOT import from: app.parser, app.api, app.services, app.engine
"""

from __future__ import annotations

from datetime import date

from app.models.company_data import CompanyData
from app.models.enums import RuleCategory, Verdict
from app.models.rule_result import RuleMetadata, RuleResult
from app.rules.base_rule import BaseRule

_EFFECTIVE_DATE_COMPANIES_ACT = date(2014, 4, 1)
_EFFECTIVE_DATE_LODR = date(2015, 9, 2)

_SEBI_LODR_URL = (
    "https://www.sebi.gov.in/legal/regulations/sep-2015/sebi-lodr-regulations-2015.html"
)


class BoardIndependenceRule(BaseRule):
    """Advisory rule: board must have sufficient independent directors.

    Companies Act 2013 s.149 and SEBI LODR Reg. 17 require:
      - At least 1/3 independent directors if the chairperson is non-executive.
      - At least 1/2 independent directors if the chairperson is executive
        OR is a promoter.

    This is an advisory check — failure flags a governance gap for human review
    but does not block IPO eligibility.

    Rule ID: BOARD_INDEPENDENCE
    """

    @property
    def rule_id(self) -> str:
        """Return the unique identifier for this rule."""
        return "BOARD_INDEPENDENCE"

    @property
    def metadata(self) -> RuleMetadata:
        """Return regulatory metadata for this rule."""
        return RuleMetadata(
            regulation="Companies Act, 2013 / SEBI (LODR) Regulations, 2015",
            section="Section 149 / Regulation 17",
            clause=None,
            description=(
                "Board must have \u2265 1/3 independent directors (non-exec chair) "
                "or \u2265 1/2 independent directors (exec or promoter chair)"
            ),
            category=RuleCategory.ADVISORY,
            effective_date=_EFFECTIVE_DATE_LODR,
            source_url=_SEBI_LODR_URL,
        )

    @property
    def _required_value(self) -> str:
        return (
            "\u2265 1/3 independent directors if non-executive chair; "
            "\u2265 1/2 if executive or promoter chair"
        )

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate board independence requirements.

        Args:
            company: The canonical company schema.

        Returns:
            PASS if independence ratio meets requirement, FAIL if not,
            INCONCLUSIVE if data quality is insufficient.
        """
        gov = company.governance

        # Reliability checks
        if not gov.total_directors.is_reliable():
            return self._build_inconclusive(
                "total_directors has LOW confidence and has not been human-confirmed"
            )
        if not gov.independent_directors.is_reliable():
            return self._build_inconclusive(
                "independent_directors has LOW confidence and has not been human-confirmed"
            )
        if not gov.is_chair_executive.is_reliable():
            return self._build_inconclusive(
                "is_chair_executive has LOW confidence and has not been human-confirmed"
            )
        if not gov.is_chair_promoter.is_reliable():
            return self._build_inconclusive(
                "is_chair_promoter has LOW confidence and has not been human-confirmed"
            )

        total = gov.total_directors.value
        independent = gov.independent_directors.value
        is_exec_chair = gov.is_chair_executive.value
        is_promoter_chair = gov.is_chair_promoter.value

        if total <= 0:
            return self._build_inconclusive(
                f"total_directors is {total}, which is invalid"
            )

        # Determine required ratio based on chair type
        requires_half = is_exec_chair or is_promoter_chair
        actual_value = (
            f"{independent} of {total} directors are independent "
            f"(chair: {'executive' if is_exec_chair else 'non-executive'}"
            f"{', promoter' if is_promoter_chair else ''})"
        )

        if requires_half:
            # Need at least half (ceiling division: independent * 2 >= total)
            passes = (independent * 2) >= total
            gap = (
                None
                if passes
                else (
                    f"{independent} of {total} independent directors "
                    f"(requires \u2265 {(total + 1) // 2} for exec/promoter chair)"
                )
            )
            explanation = (
                f"Board has {independent} independent director(s) of {total} total. "
                f"Chair is {'executive' if is_exec_chair else ''}"
                f"{'and ' if is_exec_chair and is_promoter_chair else ''}"
                f"{'promoter' if is_promoter_chair else ''}. "
                f"Requirement: at least half (\u2265 1/2) must be independent. "
                + (
                    "Requirement satisfied."
                    if passes
                    else (
                        f"Shortfall: {(total + 1) // 2 - independent} more independent "
                        "director(s) needed."
                    )
                )
            )
        else:
            # Need at least one-third (independent * 3 >= total)
            passes = (independent * 3) >= total
            needed = (total + 2) // 3  # ceiling of total/3
            gap = (
                None
                if passes
                else (
                    f"{independent} of {total} independent directors "
                    f"(requires \u2265 {needed} for non-exec chair)"
                )
            )
            explanation = (
                f"Board has {independent} independent director(s) of {total} total. "
                f"Chairperson is non-executive (non-promoter). "
                f"Requirement: at least one-third (\u2265 1/3) must be independent. "
                + (
                    "Requirement satisfied."
                    if passes
                    else f"Shortfall: {needed - independent} more independent director(s) needed."
                )
            )

        return self._build_result(
            verdict=Verdict.PASS if passes else Verdict.FAIL,
            actual_value=actual_value,
            gap=gap,
            explanation=explanation,
        )


class AuditCommitteeRule(BaseRule):
    """Advisory rule: audit committee composition must meet LODR requirements.

    SEBI LODR Regulation 18 requires:
      - Minimum 3 directors on the audit committee.
      - At least 2/3 of members must be independent directors.
      - The chairperson of the audit committee must be an independent director.

    Rule ID: AUDIT_COMMITTEE
    """

    @property
    def rule_id(self) -> str:
        """Return the unique identifier for this rule."""
        return "AUDIT_COMMITTEE"

    @property
    def metadata(self) -> RuleMetadata:
        """Return regulatory metadata for this rule."""
        return RuleMetadata(
            regulation="SEBI (LODR) Regulations, 2015",
            section="Regulation 18",
            clause=None,
            description=(
                "Audit Committee: \u2265 3 directors, \u2265 2/3 independent, "
                "chairperson must be independent"
            ),
            category=RuleCategory.ADVISORY,
            effective_date=_EFFECTIVE_DATE_LODR,
            source_url=_SEBI_LODR_URL,
        )

    @property
    def _required_value(self) -> str:
        return (
            "\u2265 3 audit committee members, \u2265 2/3 independent, "
            "chair must be independent"
        )

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate audit committee composition requirements.

        Three sub-checks are performed: member count, independence ratio,
        and chair independence. Failure of any sub-check results in FAIL
        with a detailed explanation of which requirement was not met.

        Args:
            company: The canonical company schema.

        Returns:
            PASS only if all three sub-checks pass, FAIL if any fail,
            INCONCLUSIVE if data quality is insufficient.
        """
        ac = company.governance.audit_committee

        # Reliability checks
        if not ac.total_members.is_reliable():
            return self._build_inconclusive(
                "audit_committee.total_members has LOW confidence"
            )
        if not ac.independent_members.is_reliable():
            return self._build_inconclusive(
                "audit_committee.independent_members has LOW confidence"
            )
        if not ac.chair_is_independent.is_reliable():
            return self._build_inconclusive(
                "audit_committee.chair_is_independent has LOW confidence"
            )

        total = ac.total_members.value
        independent = ac.independent_members.value
        chair_is_independent = ac.chair_is_independent.value

        failures: list[str] = []

        # Sub-check 1: Minimum 3 members
        if total < 3:
            failures.append(
                f"Insufficient members: {total} (requires \u2265 3)"
            )

        # Sub-check 2: At least 2/3 independent (independent * 3 >= total * 2)
        if total > 0 and (independent * 3) < (total * 2):
            needed = (total * 2 + 2) // 3  # ceiling of 2*total/3
            failures.append(
                f"Insufficient independent members: {independent}/{total} "
                f"(requires \u2265 2/3, i.e., \u2265 {needed})"
            )

        # Sub-check 3: Chair must be independent
        if not chair_is_independent:
            failures.append("Audit committee chairperson is not an independent director")

        actual_value = (
            f"{total} members, {independent} independent, "
            f"chair independent: {chair_is_independent}"
        )

        if failures:
            gap = "; ".join(failures)
            explanation = (
                f"Audit Committee does not meet LODR Reg. 18 requirements. "
                f"Failures: {gap}."
            )
            return self._build_result(
                verdict=Verdict.FAIL,
                actual_value=actual_value,
                gap=gap,
                explanation=explanation,
            )

        return self._build_result(
            verdict=Verdict.PASS,
            actual_value=actual_value,
            explanation=(
                f"Audit Committee meets all LODR Reg. 18 requirements: "
                f"{total} members (\u2265 3), {independent}/{total} independent "
                f"(\u2265 2/3), chair is independent."
            ),
        )
