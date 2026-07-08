"""
backend/tests/unit/rules/mandatory/test_promoter.py

Unit tests for PROMOTER_CONTRIBUTION_20 and PROMOTER_LOCK_IN mandatory rules
(SEBI ICDR Regulations 32 and 36).

100% branch coverage for PromoterContributionRule.evaluate():
  - INCONCLUSIVE: post_issue_holding has LOW confidence
  - PASS: post_issue_holding >= 20%
  - PASS: exactly 20% boundary
  - FAIL: post_issue_holding < 20%
  - Gap calculation verified

100% branch coverage for PromoterLockInRule.evaluate():
  - INCONCLUSIVE: lock_in_months has LOW confidence
  - PASS: standard issue, lock_in_months >= 18
  - PASS: capex issue, lock_in_months >= 36
  - PASS: exactly 18 months for standard issue (boundary)
  - PASS: exactly 36 months for capex issue (boundary)
  - FAIL: standard issue, lock_in_months < 18
  - FAIL: capex issue, lock_in_months < 36
  - Singular shortfall month vs plural verified
"""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import ConfidenceLevel, ExtractionMethod, Verdict
from app.models.extracted_value import ExtractedValue
from app.rules.mandatory.promoter import PromoterContributionRule, PromoterLockInRule
from tests.fixtures.company_data_factory import CompanyDataFactory


def _low_confidence_ev_decimal(value: Decimal) -> ExtractedValue[Decimal]:
    """Build a LOW-confidence OCR-extracted Decimal ExtractedValue (unreliable)."""
    return ExtractedValue(
        value=value,
        source_document="scanned_drhp.pdf",
        page_number=1,
        extraction_method=ExtractionMethod.OCR,
        confidence=ConfidenceLevel.LOW,
        confirmed_by_human=False,
    )


def _low_confidence_ev_int(value: int) -> ExtractedValue[int]:
    """Build a LOW-confidence OCR-extracted int ExtractedValue (unreliable)."""
    return ExtractedValue(
        value=value,
        source_document="scanned_drhp.pdf",
        page_number=1,
        extraction_method=ExtractionMethod.OCR,
        confidence=ConfidenceLevel.LOW,
        confirmed_by_human=False,
    )


# ---------------------------------------------------------------------------
# PromoterContributionRule tests
# ---------------------------------------------------------------------------


class TestPromoterContributionRuleMetadata:
    """Tests for PROMOTER_CONTRIBUTION_20 rule identity and metadata."""

    def test_rule_id(self) -> None:
        assert PromoterContributionRule().rule_id == "PROMOTER_CONTRIBUTION_20"

    def test_category_is_mandatory(self) -> None:
        from app.models.enums import RuleCategory

        assert PromoterContributionRule().category == RuleCategory.MANDATORY

    def test_regulation_references_sebi_icdr_reg_32(self) -> None:
        meta = PromoterContributionRule().metadata
        assert "32" in meta.section
        assert "ICDR" in meta.regulation


class TestPromoterContributionRulePass:
    """PromoterContributionRule PASS scenarios."""

    def test_75_pct_holding_passes(self) -> None:
        """Default factory: 75% post-issue holding — well above 20%."""
        company = CompanyDataFactory.create(post_issue_holding=Decimal("75"))
        result = PromoterContributionRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None
        assert result.rule_id == "PROMOTER_CONTRIBUTION_20"

    def test_exactly_20_pct_boundary_passes(self) -> None:
        """Exactly 20% is at the boundary (>= 20%)."""
        company = CompanyDataFactory.create(post_issue_holding=Decimal("20"))
        result = PromoterContributionRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None

    def test_above_20_pct_passes(self) -> None:
        """50% holding passes comfortably."""
        company = CompanyDataFactory.create(post_issue_holding=Decimal("50"))
        result = PromoterContributionRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_explanation_present_on_pass(self) -> None:
        company = CompanyDataFactory.create(post_issue_holding=Decimal("75"))
        result = PromoterContributionRule().evaluate(company)
        assert result.explanation
        assert "20" in result.explanation


class TestPromoterContributionRuleFail:
    """PromoterContributionRule FAIL scenarios."""

    def test_15_pct_holding_fails(self) -> None:
        """15% post-issue holding is below the 20% minimum."""
        company = CompanyDataFactory.create(post_issue_holding=Decimal("15"))
        result = PromoterContributionRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_just_below_20_pct_fails(self) -> None:
        """19.99% is strictly below 20%."""
        company = CompanyDataFactory.create(post_issue_holding=Decimal("19.99"))
        result = PromoterContributionRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_zero_pct_holding_fails(self) -> None:
        """0% post-issue holding fails (promoter sold all shares)."""
        company = CompanyDataFactory.create(post_issue_holding=Decimal("0"))
        result = PromoterContributionRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_gap_contains_shortfall(self) -> None:
        """Gap message must quantify the shortfall below 20%."""
        company = CompanyDataFactory.create(post_issue_holding=Decimal("15"))
        result = PromoterContributionRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        # shortfall = 20 - 15 = 5%
        assert "5.00%" in result.gap or "5.00" in result.gap

    def test_gap_contains_actual_and_required(self) -> None:
        """Gap must show both the actual holding and the 20% requirement."""
        company = CompanyDataFactory.create(post_issue_holding=Decimal("10"))
        result = PromoterContributionRule().evaluate(company)
        assert result.gap is not None
        assert "10.00%" in result.gap
        assert "20.00%" in result.gap


class TestPromoterContributionRuleInconclusive:
    """PromoterContributionRule INCONCLUSIVE scenarios."""

    def test_low_confidence_post_issue_holding_inconclusive(self) -> None:
        """Unreliable post_issue_holding → INCONCLUSIVE."""
        from app.models.company_data import PromoterData, PromoterEntity

        company_base = CompanyDataFactory.create(post_issue_holding=Decimal("75"))
        low_conf_holding = _low_confidence_ev_decimal(Decimal("75"))
        new_promoter = PromoterData(
            holding_percentage=company_base.promoter.holding_percentage,
            post_issue_holding=low_conf_holding,
            lock_in_months=company_base.promoter.lock_in_months,
            is_capex_issue=company_base.promoter.is_capex_issue,
            entities=[PromoterEntity(name="Test Promoter", holding=Decimal("75"), pan=None)],
        )
        company = company_base.model_copy(update={"promoter": new_promoter})
        result = PromoterContributionRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_inconclusive_explanation_contains_manual_review(self) -> None:
        """INCONCLUSIVE result must request manual review."""
        from app.models.company_data import PromoterData, PromoterEntity

        company_base = CompanyDataFactory.create()
        low_conf_holding = _low_confidence_ev_decimal(Decimal("75"))
        new_promoter = PromoterData(
            holding_percentage=company_base.promoter.holding_percentage,
            post_issue_holding=low_conf_holding,
            lock_in_months=company_base.promoter.lock_in_months,
            is_capex_issue=company_base.promoter.is_capex_issue,
            entities=[PromoterEntity(name="Test Promoter", holding=Decimal("75"), pan=None)],
        )
        company = company_base.model_copy(update={"promoter": new_promoter})
        result = PromoterContributionRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.explanation
        assert "manual review" in result.explanation.lower()


# ---------------------------------------------------------------------------
# PromoterLockInRule tests
# ---------------------------------------------------------------------------


class TestPromoterLockInRuleMetadata:
    """Tests for PROMOTER_LOCK_IN rule identity and metadata."""

    def test_rule_id(self) -> None:
        assert PromoterLockInRule().rule_id == "PROMOTER_LOCK_IN"

    def test_category_is_mandatory(self) -> None:
        from app.models.enums import RuleCategory

        assert PromoterLockInRule().category == RuleCategory.MANDATORY

    def test_regulation_references_sebi_icdr_reg_36(self) -> None:
        meta = PromoterLockInRule().metadata
        assert "36" in meta.section
        assert "ICDR" in meta.regulation


class TestPromoterLockInRulePassStandard:
    """PromoterLockInRule PASS scenarios for standard (non-capex) issues."""

    def test_18_months_standard_issue_passes(self) -> None:
        """Default: 18-month lock-in on a standard issue — passes at boundary."""
        company = CompanyDataFactory.create(lock_in_months=18, is_capex_issue=False)
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None
        assert result.rule_id == "PROMOTER_LOCK_IN"

    def test_exactly_18_months_boundary_passes(self) -> None:
        """Exactly 18 months satisfies >= 18 for standard issues."""
        company = CompanyDataFactory.create(lock_in_months=18, is_capex_issue=False)
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_24_months_standard_issue_passes(self) -> None:
        """24 months is above the 18-month minimum for standard issues."""
        company = CompanyDataFactory.create(lock_in_months=24, is_capex_issue=False)
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None


class TestPromoterLockInRulePassCapex:
    """PromoterLockInRule PASS scenarios for capex issues."""

    def test_36_months_capex_issue_passes(self) -> None:
        """Exactly 36-month lock-in for a capex issue — passes at boundary."""
        company = CompanyDataFactory.create(lock_in_months=36, is_capex_issue=True)
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None

    def test_exactly_36_months_boundary_capex_passes(self) -> None:
        """Exactly 36 months satisfies >= 36 for capex issues."""
        company = CompanyDataFactory.create(lock_in_months=36, is_capex_issue=True)
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_48_months_capex_issue_passes(self) -> None:
        """48 months is above the 36-month minimum for capex issues."""
        company = CompanyDataFactory.create(lock_in_months=48, is_capex_issue=True)
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.PASS


class TestPromoterLockInRuleFail:
    """PromoterLockInRule FAIL scenarios."""

    def test_12_months_standard_issue_fails(self) -> None:
        """12-month lock-in on a standard issue is below 18-month minimum."""
        company = CompanyDataFactory.create(lock_in_months=12, is_capex_issue=False)
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_just_below_18_months_standard_fails(self) -> None:
        """17 months for a standard issue is strictly below 18."""
        company = CompanyDataFactory.create(lock_in_months=17, is_capex_issue=False)
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_18_months_capex_issue_fails(self) -> None:
        """18 months is insufficient for a capex issue (requires >= 36)."""
        company = CompanyDataFactory.create(lock_in_months=18, is_capex_issue=True)
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_just_below_36_months_capex_fails(self) -> None:
        """35 months for a capex issue is strictly below 36."""
        company = CompanyDataFactory.create(lock_in_months=35, is_capex_issue=True)
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_gap_standard_issue_contains_months(self) -> None:
        """Gap for standard issue must show lock-in and required minimum."""
        company = CompanyDataFactory.create(lock_in_months=12, is_capex_issue=False)
        result = PromoterLockInRule().evaluate(company)
        assert result.gap is not None
        assert "12" in result.gap
        assert "18" in result.gap

    def test_gap_capex_issue_contains_months(self) -> None:
        """Gap for capex issue must show lock-in and required minimum."""
        company = CompanyDataFactory.create(lock_in_months=24, is_capex_issue=True)
        result = PromoterLockInRule().evaluate(company)
        assert result.gap is not None
        assert "24" in result.gap
        assert "36" in result.gap

    def test_gap_singular_shortfall_month(self) -> None:
        """When shortfall = 1, the gap should say 'month' (singular)."""
        company = CompanyDataFactory.create(lock_in_months=17, is_capex_issue=False)
        result = PromoterLockInRule().evaluate(company)
        assert result.gap is not None
        # shortfall = 18 - 17 = 1 month → singular in explanation
        assert result.explanation
        assert "1 month" in result.explanation

    def test_explanation_plural_shortfall_months(self) -> None:
        """When shortfall > 1, explanation says 'months' (plural)."""
        company = CompanyDataFactory.create(lock_in_months=12, is_capex_issue=False)
        result = PromoterLockInRule().evaluate(company)
        assert result.explanation
        # shortfall = 18 - 12 = 6 months → plural
        assert "6 months" in result.explanation


class TestPromoterLockInRuleInconclusive:
    """PromoterLockInRule INCONCLUSIVE scenarios."""

    def test_low_confidence_lock_in_months_inconclusive(self) -> None:
        """Unreliable lock_in_months → INCONCLUSIVE."""
        from app.models.company_data import PromoterData, PromoterEntity

        company_base = CompanyDataFactory.create(lock_in_months=18, is_capex_issue=False)
        low_conf_lock_in = _low_confidence_ev_int(18)
        new_promoter = PromoterData(
            holding_percentage=company_base.promoter.holding_percentage,
            post_issue_holding=company_base.promoter.post_issue_holding,
            lock_in_months=low_conf_lock_in,
            is_capex_issue=False,
            entities=[PromoterEntity(name="Test Promoter", holding=Decimal("75"), pan=None)],
        )
        company = company_base.model_copy(update={"promoter": new_promoter})
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_inconclusive_explanation_contains_manual_review(self) -> None:
        """INCONCLUSIVE result must request manual review."""
        from app.models.company_data import PromoterData, PromoterEntity

        company_base = CompanyDataFactory.create()
        low_conf_lock_in = _low_confidence_ev_int(18)
        new_promoter = PromoterData(
            holding_percentage=company_base.promoter.holding_percentage,
            post_issue_holding=company_base.promoter.post_issue_holding,
            lock_in_months=low_conf_lock_in,
            is_capex_issue=False,
            entities=[PromoterEntity(name="Test Promoter", holding=Decimal("75"), pan=None)],
        )
        company = company_base.model_copy(update={"promoter": new_promoter})
        result = PromoterLockInRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.explanation
        assert "manual review" in result.explanation.lower()
