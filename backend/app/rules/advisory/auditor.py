"""
backend/app/rules/advisory/auditor.py

Advisory rule: Auditor qualification check (AUDITOR_QUALIFICATION).

Companies Act 2013 Section 143 and SEBI's reporting requirements mandate
that statutory auditors report qualifications, modified opinions, or
emphasis of matter paragraphs. The presence of such qualifications is a
significant red flag in IPO due diligence.

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


class AuditorQualificationRule(BaseRule):
    """Advisory rule: no modified opinions or qualifications in audit reports.

    Companies Act 2013 s.143 requires statutory auditors to express their
    opinion on whether financial statements give a true and fair view. A
    qualified, adverse, or disclaimer opinion indicates material uncertainty
    or non-compliance that must be resolved before IPO.

    Rule ID: AUDITOR_QUALIFICATION
    """

    @property
    def rule_id(self) -> str:
        """Return the unique identifier for this rule."""
        return "AUDITOR_QUALIFICATION"

    @property
    def metadata(self) -> RuleMetadata:
        """Return regulatory metadata for this rule."""
        return RuleMetadata(
            regulation="Companies Act, 2013",
            section="Section 143",
            clause=None,
            description=(
                "Statutory auditor reports must be free of qualifications, "
                "modified opinions, and adverse remarks"
            ),
            category=RuleCategory.ADVISORY,
            effective_date=_EFFECTIVE_DATE_COMPANIES_ACT,
            source_url=None,
        )

    @property
    def _required_value(self) -> str:
        return (
            "No audit qualifications, no modified opinions, "
            "and no adverse remarks in financial statements"
        )

    def evaluate(self, company: CompanyData) -> RuleResult:
        """Evaluate auditor qualification status.

        Args:
            company: The canonical company schema.

        Returns:
            INCONCLUSIVE if auditor data is unreliable.
            FAIL if qualifications or modified opinions are present.
            PASS otherwise.
        """
        auditor = company.auditor

        # Reliability checks
        if not auditor.has_qualifications.is_reliable():
            return self._build_inconclusive(
                "has_qualifications has LOW confidence and has not been human-confirmed"
            )
        if not auditor.has_modified_opinion.is_reliable():
            return self._build_inconclusive(
                "has_modified_opinion has LOW confidence and has not been human-confirmed"
            )

        has_qual = auditor.has_qualifications.value
        has_modified = auditor.has_modified_opinion.value
        auditor_name = auditor.auditor_name

        actual_value = (
            f"Auditor: {auditor_name}; "
            f"Qualifications: {'Yes' if has_qual else 'No'}; "
            f"Modified opinion: {'Yes' if has_modified else 'No'}"
        )

        issues: list[str] = []
        if has_qual:
            issues.append("audit report contains qualifications or emphasis of matter")
        if has_modified:
            issues.append("auditor has issued a modified opinion (qualified/adverse/disclaimer)")

        if issues:
            gap = "; ".join(issues).capitalize()
            return self._build_result(
                verdict=Verdict.FAIL,
                actual_value=actual_value,
                gap=gap,
                explanation=(
                    f"Auditor {auditor_name!r} has issued a report with concerns: "
                    f"{gap}. IPO applicants are expected to have clean audit reports. "
                    "Resolve all qualifications and obtain unmodified opinions before filing."
                ),
            )

        return self._build_result(
            verdict=Verdict.PASS,
            actual_value=actual_value,
            explanation=(
                f"Statutory auditor {auditor_name!r} has issued an unmodified opinion "
                "with no qualifications or emphasis of matter paragraphs. "
                "Audit report is clean per Companies Act s.143 requirements."
            ),
        )
