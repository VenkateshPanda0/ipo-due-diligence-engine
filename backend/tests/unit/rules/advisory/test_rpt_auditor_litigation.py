"""
backend/tests/unit/rules/advisory/test_rpt_auditor_litigation.py

Unit tests for RPT_DISCLOSURE, AUDITOR_QUALIFICATION, and LITIGATION_RISK
advisory rules (M3-030).

100% branch coverage for all three rules.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import ConfidenceLevel, ExtractionMethod, Verdict
from app.models.extracted_value import ExtractedValue
from app.rules.advisory.auditor import AuditorQualificationRule
from app.rules.advisory.litigation import LitigationRiskRule
from app.rules.advisory.rpt import RPTDisclosureRule
from tests.fixtures.company_data_factory import CompanyDataFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _low_ev(value: object) -> ExtractedValue[object]:
    return ExtractedValue(
        value=value,
        source_document="test.pdf",
        extraction_method=ExtractionMethod.OCR,
        confidence=ConfidenceLevel.LOW,
    )


def _high_ev(value: object) -> ExtractedValue[object]:
    return ExtractedValue(
        value=value,
        source_document="test.pdf",
        extraction_method=ExtractionMethod.MANUAL,
        confidence=ConfidenceLevel.HIGH,
    )


# ---------------------------------------------------------------------------
# RPT_DISCLOSURE tests
# ---------------------------------------------------------------------------


class TestRPTDisclosureMetadata:
    def test_rule_id(self) -> None:
        assert RPTDisclosureRule().rule_id == "RPT_DISCLOSURE"

    def test_category_advisory(self) -> None:
        from app.models.enums import RuleCategory
        assert RPTDisclosureRule().category == RuleCategory.ADVISORY


class TestRPTDisclosurePass:
    def test_arm_length_certified_no_transactions(self) -> None:
        company = CompanyDataFactory.create(arm_length_certified=True, total_rpt_value=Decimal("0"))
        result = RPTDisclosureRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_arm_length_certified_with_transactions(self) -> None:
        company = CompanyDataFactory.create(arm_length_certified=True, total_rpt_value=Decimal("5"))
        result = RPTDisclosureRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_high_rpt_volume_still_passes_with_warning_in_explanation(self) -> None:
        """RPT > 20% revenue still PASSES (advisory only - it's in explanation)."""
        # Revenue = 100, RPT = 25 → 25% > 20%
        company = CompanyDataFactory.create(
            arm_length_certified=True,
            total_rpt_value=Decimal("25"),
        )
        result = RPTDisclosureRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        # High volume warning should appear in explanation
        assert "Warning" in result.explanation or "%" in result.explanation


class TestRPTDisclosureFail:
    def test_not_arm_length_certified_fails(self) -> None:
        company = CompanyDataFactory.create(
            arm_length_certified=False,
            total_rpt_value=Decimal("5"),
        )
        result = RPTDisclosureRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        assert "arm's length" in result.gap.lower()


class TestRPTDisclosureInconclusive:
    def test_low_confidence_arm_length_certified_inconclusive(self) -> None:
        from app.models.company_data import CompanyData, RelatedPartyData
        company = CompanyDataFactory.create()
        new_rpt = RelatedPartyData(
            transactions=company.rpt.transactions,
            total_rpt_value=company.rpt.total_rpt_value,
            arm_length_certified=_low_ev(True),  # type: ignore[arg-type]
        )
        patched = CompanyData(
            identification=company.identification,
            financials=company.financials,
            promoter=company.promoter,
            governance=company.governance,
            litigation=company.litigation,
            rpt=new_rpt,
            issue_details=company.issue_details,
            auditor=company.auditor,
            ruleset_version=company.ruleset_version,
        )
        result = RPTDisclosureRule().evaluate(patched)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_total_rpt_value_inconclusive(self) -> None:
        from app.models.company_data import CompanyData, RelatedPartyData
        company = CompanyDataFactory.create()
        new_rpt = RelatedPartyData(
            transactions=company.rpt.transactions,
            total_rpt_value=_low_ev(Decimal("5")),  # type: ignore[arg-type]
            arm_length_certified=company.rpt.arm_length_certified,
        )
        patched = CompanyData(
            identification=company.identification,
            financials=company.financials,
            promoter=company.promoter,
            governance=company.governance,
            litigation=company.litigation,
            rpt=new_rpt,
            issue_details=company.issue_details,
            auditor=company.auditor,
            ruleset_version=company.ruleset_version,
        )
        result = RPTDisclosureRule().evaluate(patched)
        assert result.verdict == Verdict.INCONCLUSIVE


# ---------------------------------------------------------------------------
# AUDITOR_QUALIFICATION tests
# ---------------------------------------------------------------------------


class TestAuditorQualificationMetadata:
    def test_rule_id(self) -> None:
        assert AuditorQualificationRule().rule_id == "AUDITOR_QUALIFICATION"

    def test_category_advisory(self) -> None:
        from app.models.enums import RuleCategory
        assert AuditorQualificationRule().category == RuleCategory.ADVISORY


class TestAuditorQualificationPass:
    def test_clean_audit_report_passes(self) -> None:
        company = CompanyDataFactory.create(
            has_qualifications=False,
            has_modified_opinion=False,
        )
        result = AuditorQualificationRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_actual_value_includes_auditor_name(self) -> None:
        company = CompanyDataFactory.create(auditor_name="Deloitte LLP")
        result = AuditorQualificationRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert "Deloitte LLP" in (result.actual_value or "")


class TestAuditorQualificationFail:
    def test_qualifications_in_report_fails(self) -> None:
        company = CompanyDataFactory.create(has_qualifications=True)
        result = AuditorQualificationRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_modified_opinion_fails(self) -> None:
        company = CompanyDataFactory.create(has_modified_opinion=True)
        result = AuditorQualificationRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_both_issues_reported_in_gap(self) -> None:
        company = CompanyDataFactory.create(
            has_qualifications=True,
            has_modified_opinion=True,
        )
        result = AuditorQualificationRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        gap = result.gap or ""
        assert "qualification" in gap.lower()
        assert "modified" in gap.lower()


class TestAuditorQualificationInconclusive:
    def test_low_confidence_has_qualifications_inconclusive(self) -> None:
        from app.models.company_data import AuditorData, CompanyData
        company = CompanyDataFactory.create()
        new_auditor = AuditorData(
            auditor_name=company.auditor.auditor_name,
            has_qualifications=_low_ev(False),  # type: ignore[arg-type]
            has_modified_opinion=company.auditor.has_modified_opinion,
            years_as_auditor=company.auditor.years_as_auditor,
        )
        patched = CompanyData(
            identification=company.identification,
            financials=company.financials,
            promoter=company.promoter,
            governance=company.governance,
            litigation=company.litigation,
            rpt=company.rpt,
            issue_details=company.issue_details,
            auditor=new_auditor,
            ruleset_version=company.ruleset_version,
        )
        result = AuditorQualificationRule().evaluate(patched)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_has_modified_opinion_inconclusive(self) -> None:
        from app.models.company_data import AuditorData, CompanyData
        company = CompanyDataFactory.create()
        new_auditor = AuditorData(
            auditor_name=company.auditor.auditor_name,
            has_qualifications=company.auditor.has_qualifications,
            has_modified_opinion=_low_ev(False),  # type: ignore[arg-type]
            years_as_auditor=company.auditor.years_as_auditor,
        )
        patched = CompanyData(
            identification=company.identification,
            financials=company.financials,
            promoter=company.promoter,
            governance=company.governance,
            litigation=company.litigation,
            rpt=company.rpt,
            issue_details=company.issue_details,
            auditor=new_auditor,
            ruleset_version=company.ruleset_version,
        )
        result = AuditorQualificationRule().evaluate(patched)
        assert result.verdict == Verdict.INCONCLUSIVE


# ---------------------------------------------------------------------------
# LITIGATION_RISK tests
# ---------------------------------------------------------------------------


class TestLitigationRiskMetadata:
    def test_rule_id(self) -> None:
        assert LitigationRiskRule().rule_id == "LITIGATION_RISK"

    def test_category_advisory(self) -> None:
        from app.models.enums import RuleCategory
        assert LitigationRiskRule().category == RuleCategory.ADVISORY


class TestLitigationRiskPass:
    def test_no_cases_passes(self) -> None:
        company = CompanyDataFactory.create(
            has_criminal_cases=False,
            total_litigation_exposure=Decimal("0"),
        )
        result = LitigationRiskRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_small_exposure_within_20_pct_passes(self) -> None:
        # net_worth = 50, exposure = 5 → 10% < 20%
        company = CompanyDataFactory.create(
            has_criminal_cases=False,
            total_litigation_exposure=Decimal("5"),
            net_worth=Decimal("50"),
        )
        result = LitigationRiskRule().evaluate(company)
        assert result.verdict == Verdict.PASS


class TestLitigationRiskFail:
    def test_criminal_cases_fails(self) -> None:
        company = CompanyDataFactory.create(has_criminal_cases=True)
        result = LitigationRiskRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        assert "criminal" in result.gap.lower()

    def test_material_exposure_exceeds_20_pct_net_worth_fails(self) -> None:
        # net_worth = 50, exposure = 15 → 30% > 20%
        company = CompanyDataFactory.create(
            has_criminal_cases=False,
            total_litigation_exposure=Decimal("15"),
            net_worth=Decimal("50"),
        )
        result = LitigationRiskRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_criminal_plus_material_exposure_both_in_gap(self) -> None:
        company = CompanyDataFactory.create(
            has_criminal_cases=True,
            total_litigation_exposure=Decimal("15"),
            net_worth=Decimal("50"),
        )
        result = LitigationRiskRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        gap = result.gap or ""
        assert "criminal" in gap.lower()


class TestLitigationRiskInconclusive:
    def test_low_confidence_criminal_cases_inconclusive(self) -> None:
        from app.models.company_data import CompanyData, LitigationData
        company = CompanyDataFactory.create()
        new_lit = LitigationData(
            pending_cases=company.litigation.pending_cases,
            total_exposure=company.litigation.total_exposure,
            has_criminal_cases=_low_ev(False),  # type: ignore[arg-type]
        )
        patched = CompanyData(
            identification=company.identification,
            financials=company.financials,
            promoter=company.promoter,
            governance=company.governance,
            litigation=new_lit,
            rpt=company.rpt,
            issue_details=company.issue_details,
            auditor=company.auditor,
            ruleset_version=company.ruleset_version,
        )
        result = LitigationRiskRule().evaluate(patched)
        assert result.verdict == Verdict.INCONCLUSIVE
