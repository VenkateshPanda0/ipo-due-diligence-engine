"""
backend/tests/unit/rules/advisory/test_governance.py

Unit tests for BOARD_INDEPENDENCE and AUDIT_COMMITTEE advisory rules (M3-029).

100% branch coverage for both rules including:
  - BoardIndependenceRule: 1/3 threshold (non-exec chair), 1/2 threshold (exec/promoter chair)
  - AuditCommitteeRule: count check, ratio check, chair independence check
  - INCONCLUSIVE paths for LOW confidence data
  - Fractional comparisons at exact boundaries
"""

from __future__ import annotations

from app.models.enums import Verdict
from app.rules.advisory.governance import AuditCommitteeRule, BoardIndependenceRule
from tests.fixtures.company_data_factory import CompanyDataFactory


class TestBoardIndependenceRuleMetadata:
    def test_rule_id(self) -> None:
        assert BoardIndependenceRule().rule_id == "BOARD_INDEPENDENCE"

    def test_category_advisory(self) -> None:
        from app.models.enums import RuleCategory
        assert BoardIndependenceRule().category == RuleCategory.ADVISORY


class TestBoardIndependenceNonExecChair:
    """Tests for non-executive, non-promoter chair (≥ 1/3 threshold)."""

    def test_exactly_one_third_passes(self) -> None:
        # 6 directors, 2 independent = 2/6 = 1/3 exactly
        company = CompanyDataFactory.create(
            total_directors=6,
            independent_directors=2,
            is_chair_executive=False,
            is_chair_promoter=False,
        )
        result = BoardIndependenceRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_above_one_third_passes(self) -> None:
        # 6 directors, 3 independent = 50% > 1/3
        company = CompanyDataFactory.create(
            total_directors=6,
            independent_directors=3,
            is_chair_executive=False,
            is_chair_promoter=False,
        )
        result = BoardIndependenceRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_below_one_third_fails(self) -> None:
        # 6 directors, 1 independent = 1/6 < 1/3
        company = CompanyDataFactory.create(
            total_directors=6,
            independent_directors=1,
            is_chair_executive=False,
            is_chair_promoter=False,
        )
        result = BoardIndependenceRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_zero_independent_fails(self) -> None:
        company = CompanyDataFactory.create(
            total_directors=6,
            independent_directors=0,
            is_chair_executive=False,
            is_chair_promoter=False,
        )
        result = BoardIndependenceRule().evaluate(company)
        assert result.verdict == Verdict.FAIL


class TestBoardIndependenceExecOrPromoterChair:
    """Tests for executive or promoter chair (≥ 1/2 threshold)."""

    def test_exec_chair_exactly_half_passes(self) -> None:
        # 6 directors, 3 independent = 3/6 = 1/2 exactly
        company = CompanyDataFactory.create(
            total_directors=6,
            independent_directors=3,
            is_chair_executive=True,
            is_chair_promoter=False,
        )
        result = BoardIndependenceRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_exec_chair_below_half_fails(self) -> None:
        # 6 directors, 2 independent = 2/6 = 1/3 < 1/2
        company = CompanyDataFactory.create(
            total_directors=6,
            independent_directors=2,
            is_chair_executive=True,
            is_chair_promoter=False,
        )
        result = BoardIndependenceRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_promoter_chair_triggers_half_requirement(self) -> None:
        # Promoter chair: same as exec chair - needs 1/2
        company = CompanyDataFactory.create(
            total_directors=4,
            independent_directors=1,  # 1/4 < 1/2
            is_chair_executive=False,
            is_chair_promoter=True,
        )
        result = BoardIndependenceRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_both_exec_and_promoter_chair_half_required(self) -> None:
        company = CompanyDataFactory.create(
            total_directors=4,
            independent_directors=2,  # 2/4 = 1/2 exactly
            is_chair_executive=True,
            is_chair_promoter=True,
        )
        result = BoardIndependenceRule().evaluate(company)
        assert result.verdict == Verdict.PASS


class TestBoardIndependenceInconclusive:
    """INCONCLUSIVE paths for board independence rule."""

    def test_zero_total_directors_inconclusive(self) -> None:
        company = CompanyDataFactory.create(total_directors=0, independent_directors=0)
        result = BoardIndependenceRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_total_directors_inconclusive(self) -> None:
        from app.models.company_data import GovernanceData
        from app.models.enums import ConfidenceLevel, ExtractionMethod
        from app.models.extracted_value import ExtractedValue

        # Create a company with LOW confidence total_directors.
        bad_company = CompanyDataFactory.create(total_directors=6, independent_directors=3)
        # Patch via factory: we need to create a custom GovernanceData
        from app.models.company_data import CompanyData

        low_ev = ExtractedValue(
            value=6,
            source_document="test.pdf",
            extraction_method=ExtractionMethod.OCR,
            confidence=ConfidenceLevel.LOW,
        )
        new_gov = GovernanceData(
            total_directors=low_ev,
            independent_directors=bad_company.governance.independent_directors,
            is_chair_executive=bad_company.governance.is_chair_executive,
            is_chair_promoter=bad_company.governance.is_chair_promoter,
            audit_committee=bad_company.governance.audit_committee,
        )
        patched = CompanyData(
            identification=bad_company.identification,
            financials=bad_company.financials,
            promoter=bad_company.promoter,
            governance=new_gov,
            litigation=bad_company.litigation,
            rpt=bad_company.rpt,
            issue_details=bad_company.issue_details,
            auditor=bad_company.auditor,
            ruleset_version=bad_company.ruleset_version,
        )
        result = BoardIndependenceRule().evaluate(patched)
        assert result.verdict == Verdict.INCONCLUSIVE


class TestAuditCommitteeRuleMetadata:
    def test_rule_id(self) -> None:
        assert AuditCommitteeRule().rule_id == "AUDIT_COMMITTEE"

    def test_category_advisory(self) -> None:
        from app.models.enums import RuleCategory
        assert AuditCommitteeRule().category == RuleCategory.ADVISORY


class TestAuditCommitteePass:
    def test_all_three_requirements_met(self) -> None:
        # 4 members, 3 independent (3/4 > 2/3), chair independent
        company = CompanyDataFactory.create(
            audit_total_members=4,
            audit_independent_members=3,
            audit_chair_is_independent=True,
        )
        result = AuditCommitteeRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_exactly_3_members_exactly_2_third_independent(self) -> None:
        # 3 members, 2 independent = 2/3 exactly, chair independent
        company = CompanyDataFactory.create(
            audit_total_members=3,
            audit_independent_members=2,
            audit_chair_is_independent=True,
        )
        result = AuditCommitteeRule().evaluate(company)
        assert result.verdict == Verdict.PASS


class TestAuditCommitteeFail:
    def test_too_few_members_fails(self) -> None:
        # Only 2 members — below minimum of 3
        company = CompanyDataFactory.create(
            audit_total_members=2,
            audit_independent_members=2,
            audit_chair_is_independent=True,
        )
        result = AuditCommitteeRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        assert "3" in result.gap

    def test_insufficient_independent_fails(self) -> None:
        # 3 members, only 1 independent = 1/3 < 2/3
        company = CompanyDataFactory.create(
            audit_total_members=3,
            audit_independent_members=1,
            audit_chair_is_independent=True,
        )
        result = AuditCommitteeRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_chair_not_independent_fails(self) -> None:
        # Good count and ratio, but chair is not independent
        company = CompanyDataFactory.create(
            audit_total_members=4,
            audit_independent_members=3,
            audit_chair_is_independent=False,
        )
        result = AuditCommitteeRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_multiple_failures_all_reported_in_gap(self) -> None:
        # All three sub-checks fail
        company = CompanyDataFactory.create(
            audit_total_members=2,
            audit_independent_members=0,
            audit_chair_is_independent=False,
        )
        result = AuditCommitteeRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        gap = result.gap or ""
        assert "Insufficient members" in gap
        assert "chairperson" in gap


class TestAuditCommitteeInconclusive:
    def test_low_confidence_total_members_inconclusive(self) -> None:
        from app.models.company_data import AuditCommittee, CompanyData, GovernanceData
        from app.models.enums import ConfidenceLevel, ExtractionMethod
        from app.models.extracted_value import ExtractedValue

        company = CompanyDataFactory.create()
        low_ev = ExtractedValue(
            value=4,
            source_document="test.pdf",
            extraction_method=ExtractionMethod.OCR,
            confidence=ConfidenceLevel.LOW,
        )
        new_ac = AuditCommittee(
            total_members=low_ev,
            independent_members=company.governance.audit_committee.independent_members,
            chair_is_independent=company.governance.audit_committee.chair_is_independent,
        )
        new_gov = GovernanceData(
            total_directors=company.governance.total_directors,
            independent_directors=company.governance.independent_directors,
            is_chair_executive=company.governance.is_chair_executive,
            is_chair_promoter=company.governance.is_chair_promoter,
            audit_committee=new_ac,
        )
        patched = CompanyData(
            identification=company.identification,
            financials=company.financials,
            promoter=company.promoter,
            governance=new_gov,
            litigation=company.litigation,
            rpt=company.rpt,
            issue_details=company.issue_details,
            auditor=company.auditor,
            ruleset_version=company.ruleset_version,
        )
        result = AuditCommitteeRule().evaluate(patched)
        assert result.verdict == Verdict.INCONCLUSIVE
