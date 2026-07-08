"""
backend/tests/unit/rules/mandatory/test_minimum_capital.py

Unit tests for MIN_POST_ISSUE_CAPITAL and MIN_MARKET_CAP mandatory rules
(NSE/BSE Listing Requirements).

100% branch coverage for MinPostIssueCapitalRule.evaluate():
  - INCONCLUSIVE: post_issue_paid_up_capital has LOW confidence
  - PASS: capital >= Rs 10 Cr
  - PASS: exactly Rs 10 Cr boundary
  - FAIL: capital < Rs 10 Cr
  - Gap calculation verified

100% branch coverage for MinMarketCapRule.evaluate():
  - INCONCLUSIVE: expected_market_cap has LOW confidence
  - PASS: market cap >= Rs 25 Cr
  - PASS: exactly Rs 25 Cr boundary
  - FAIL: market cap < Rs 25 Cr
  - Gap calculation verified
"""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import ConfidenceLevel, ExtractionMethod, Verdict
from app.models.extracted_value import ExtractedValue
from app.rules.mandatory.minimum_capital import MinMarketCapRule, MinPostIssueCapitalRule
from tests.fixtures.company_data_factory import CompanyDataFactory


def _low_confidence_ev(value: Decimal) -> ExtractedValue[Decimal]:
    """Build a LOW-confidence OCR-extracted ExtractedValue (unreliable)."""
    return ExtractedValue(
        value=value,
        source_document="scanned_prospectus.pdf",
        page_number=1,
        extraction_method=ExtractionMethod.OCR,
        confidence=ConfidenceLevel.LOW,
        confirmed_by_human=False,
    )


# ---------------------------------------------------------------------------
# MinPostIssueCapitalRule tests
# ---------------------------------------------------------------------------


class TestMinPostIssueCapitalRuleMetadata:
    """Tests for MIN_POST_ISSUE_CAPITAL rule identity and metadata."""

    def test_rule_id(self) -> None:
        assert MinPostIssueCapitalRule().rule_id == "MIN_POST_ISSUE_CAPITAL"

    def test_category_is_mandatory(self) -> None:
        from app.models.enums import RuleCategory

        assert MinPostIssueCapitalRule().category == RuleCategory.MANDATORY

    def test_regulation_references_nse_bse(self) -> None:
        meta = MinPostIssueCapitalRule().metadata
        assert "NSE" in meta.regulation or "BSE" in meta.regulation or "Listing" in meta.regulation


class TestMinPostIssueCapitalRulePass:
    """MinPostIssueCapitalRule PASS scenarios."""

    def test_15cr_capital_passes(self) -> None:
        """Default factory: Rs 15 Cr post-issue paid-up capital — passes."""
        company = CompanyDataFactory.create(post_issue_paid_up_capital=Decimal("15"))
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None
        assert result.rule_id == "MIN_POST_ISSUE_CAPITAL"

    def test_exactly_10cr_boundary_passes(self) -> None:
        """Exactly Rs 10 Cr is at the boundary (>= 10)."""
        company = CompanyDataFactory.create(post_issue_paid_up_capital=Decimal("10"))
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None

    def test_large_capital_passes(self) -> None:
        """Rs 500 Cr post-issue capital passes comfortably."""
        company = CompanyDataFactory.create(post_issue_paid_up_capital=Decimal("500"))
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_explanation_present_on_pass(self) -> None:
        company = CompanyDataFactory.create(post_issue_paid_up_capital=Decimal("20"))
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.explanation
        assert "10" in result.explanation


class TestMinPostIssueCapitalRuleFail:
    """MinPostIssueCapitalRule FAIL scenarios."""

    def test_5cr_capital_fails(self) -> None:
        """Rs 5 Cr post-issue capital is below the Rs 10 Cr floor."""
        company = CompanyDataFactory.create(post_issue_paid_up_capital=Decimal("5"))
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_just_below_10cr_fails(self) -> None:
        """Rs 9.99 Cr is strictly below Rs 10 Cr."""
        company = CompanyDataFactory.create(post_issue_paid_up_capital=Decimal("9.99"))
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_zero_capital_fails(self) -> None:
        """Rs 0 Cr post-issue capital fails."""
        company = CompanyDataFactory.create(post_issue_paid_up_capital=Decimal("0"))
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_gap_contains_actual_and_required_amounts(self) -> None:
        """Gap message must contain the actual capital and the Rs 10 Cr floor."""
        company = CompanyDataFactory.create(post_issue_paid_up_capital=Decimal("5"))
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.gap is not None
        assert "5.00" in result.gap
        assert "10" in result.gap

    def test_gap_shortfall_correctly_quantified(self) -> None:
        """Explanation must contain the shortfall amount."""
        company = CompanyDataFactory.create(post_issue_paid_up_capital=Decimal("7"))
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        # shortfall = 10 - 7 = 3 Cr
        assert result.explanation
        assert "3.00" in result.explanation


class TestMinPostIssueCapitalRuleInconclusive:
    """MinPostIssueCapitalRule INCONCLUSIVE scenarios."""

    def test_low_confidence_capital_inconclusive(self) -> None:
        """Unreliable post_issue_paid_up_capital → INCONCLUSIVE."""
        from app.models.company_data import IssueDetails

        company_base = CompanyDataFactory.create(post_issue_paid_up_capital=Decimal("15"))
        low_conf_capital = _low_confidence_ev(Decimal("15"))
        new_issue_details = IssueDetails(
            issue_size=company_base.issue_details.issue_size,
            pre_issue_net_worth=company_base.issue_details.pre_issue_net_worth,
            post_issue_paid_up_capital=low_conf_capital,
            expected_market_cap=company_base.issue_details.expected_market_cap,
            public_offer_percentage=company_base.issue_details.public_offer_percentage,
            issue_type=company_base.issue_details.issue_type,
        )
        company = company_base.model_copy(update={"issue_details": new_issue_details})
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_inconclusive_explanation_contains_manual_review(self) -> None:
        """INCONCLUSIVE result must request manual review."""
        from app.models.company_data import IssueDetails

        company_base = CompanyDataFactory.create()
        low_conf_capital = _low_confidence_ev(Decimal("15"))
        new_issue_details = IssueDetails(
            issue_size=company_base.issue_details.issue_size,
            pre_issue_net_worth=company_base.issue_details.pre_issue_net_worth,
            post_issue_paid_up_capital=low_conf_capital,
            expected_market_cap=company_base.issue_details.expected_market_cap,
            public_offer_percentage=company_base.issue_details.public_offer_percentage,
            issue_type=company_base.issue_details.issue_type,
        )
        company = company_base.model_copy(update={"issue_details": new_issue_details})
        result = MinPostIssueCapitalRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.explanation
        assert "manual review" in result.explanation.lower()


# ---------------------------------------------------------------------------
# MinMarketCapRule tests
# ---------------------------------------------------------------------------


class TestMinMarketCapRuleMetadata:
    """Tests for MIN_MARKET_CAP rule identity and metadata."""

    def test_rule_id(self) -> None:
        assert MinMarketCapRule().rule_id == "MIN_MARKET_CAP"

    def test_category_is_mandatory(self) -> None:
        from app.models.enums import RuleCategory

        assert MinMarketCapRule().category == RuleCategory.MANDATORY

    def test_regulation_references_nse_bse(self) -> None:
        meta = MinMarketCapRule().metadata
        assert "NSE" in meta.regulation or "BSE" in meta.regulation or "Listing" in meta.regulation


class TestMinMarketCapRulePass:
    """MinMarketCapRule PASS scenarios."""

    def test_800cr_market_cap_passes(self) -> None:
        """Default factory: Rs 800 Cr expected market cap — passes."""
        company = CompanyDataFactory.create(expected_market_cap=Decimal("800"))
        result = MinMarketCapRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None
        assert result.rule_id == "MIN_MARKET_CAP"

    def test_exactly_25cr_boundary_passes(self) -> None:
        """Exactly Rs 25 Cr is at the boundary (>= 25)."""
        company = CompanyDataFactory.create(expected_market_cap=Decimal("25"))
        result = MinMarketCapRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None

    def test_large_market_cap_passes(self) -> None:
        """Rs 10000 Cr market cap passes comfortably."""
        company = CompanyDataFactory.create(expected_market_cap=Decimal("10000"))
        result = MinMarketCapRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_explanation_present_on_pass(self) -> None:
        company = CompanyDataFactory.create(expected_market_cap=Decimal("50"))
        result = MinMarketCapRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.explanation
        assert "25" in result.explanation


class TestMinMarketCapRuleFail:
    """MinMarketCapRule FAIL scenarios."""

    def test_10cr_market_cap_fails(self) -> None:
        """Rs 10 Cr expected market cap is below the Rs 25 Cr floor."""
        company = CompanyDataFactory.create(expected_market_cap=Decimal("10"))
        result = MinMarketCapRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_just_below_25cr_fails(self) -> None:
        """Rs 24.99 Cr is strictly below Rs 25 Cr."""
        company = CompanyDataFactory.create(expected_market_cap=Decimal("24.99"))
        result = MinMarketCapRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_zero_market_cap_fails(self) -> None:
        """Rs 0 Cr expected market cap fails."""
        company = CompanyDataFactory.create(expected_market_cap=Decimal("0"))
        result = MinMarketCapRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_gap_contains_actual_and_required_amounts(self) -> None:
        """Gap message must contain the actual cap and the Rs 25 Cr floor."""
        company = CompanyDataFactory.create(expected_market_cap=Decimal("10"))
        result = MinMarketCapRule().evaluate(company)
        assert result.gap is not None
        assert "10.00" in result.gap
        assert "25" in result.gap

    def test_gap_shortfall_correctly_quantified(self) -> None:
        """Explanation must quantify the shortfall from the Rs 25 Cr floor."""
        company = CompanyDataFactory.create(expected_market_cap=Decimal("20"))
        result = MinMarketCapRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        # shortfall = 25 - 20 = 5 Cr
        assert result.explanation
        assert "5.00" in result.explanation


class TestMinMarketCapRuleInconclusive:
    """MinMarketCapRule INCONCLUSIVE scenarios."""

    def test_low_confidence_market_cap_inconclusive(self) -> None:
        """Unreliable expected_market_cap → INCONCLUSIVE."""
        from app.models.company_data import IssueDetails

        company_base = CompanyDataFactory.create(expected_market_cap=Decimal("800"))
        low_conf_market_cap = _low_confidence_ev(Decimal("800"))
        new_issue_details = IssueDetails(
            issue_size=company_base.issue_details.issue_size,
            pre_issue_net_worth=company_base.issue_details.pre_issue_net_worth,
            post_issue_paid_up_capital=company_base.issue_details.post_issue_paid_up_capital,
            expected_market_cap=low_conf_market_cap,
            public_offer_percentage=company_base.issue_details.public_offer_percentage,
            issue_type=company_base.issue_details.issue_type,
        )
        company = company_base.model_copy(update={"issue_details": new_issue_details})
        result = MinMarketCapRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_inconclusive_explanation_contains_manual_review(self) -> None:
        """INCONCLUSIVE result must request manual review."""
        from app.models.company_data import IssueDetails

        company_base = CompanyDataFactory.create()
        low_conf_market_cap = _low_confidence_ev(Decimal("800"))
        new_issue_details = IssueDetails(
            issue_size=company_base.issue_details.issue_size,
            pre_issue_net_worth=company_base.issue_details.pre_issue_net_worth,
            post_issue_paid_up_capital=company_base.issue_details.post_issue_paid_up_capital,
            expected_market_cap=low_conf_market_cap,
            public_offer_percentage=company_base.issue_details.public_offer_percentage,
            issue_type=company_base.issue_details.issue_type,
        )
        company = company_base.model_copy(update={"issue_details": new_issue_details})
        result = MinMarketCapRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.explanation
        assert "manual review" in result.explanation.lower()
