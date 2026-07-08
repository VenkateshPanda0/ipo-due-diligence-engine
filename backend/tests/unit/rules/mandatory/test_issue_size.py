"""
backend/tests/unit/rules/mandatory/test_issue_size.py

Unit tests for ISSUE_SIZE_5X mandatory rule (SEBI ICDR Regulation 26(2)).

100% branch coverage for IssueSizeRule.evaluate():
  - INCONCLUSIVE: issue_size has LOW confidence
  - INCONCLUSIVE: pre_issue_net_worth has LOW confidence
  - FAIL: pre_issue_net_worth <= 0 (zero net worth)
  - FAIL: pre_issue_net_worth < 0 (negative net worth)
  - PASS: issue_size <= 5 * pre_issue_net_worth
  - PASS: exactly 5x boundary (issue_size == 5 * pre_issue_net_worth)
  - FAIL: issue_size > 5 * pre_issue_net_worth
  - Gap calculation verification
"""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import ConfidenceLevel, ExtractionMethod, Verdict
from app.models.extracted_value import ExtractedValue
from app.rules.mandatory.issue_size import IssueSizeRule
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


class TestIssueSizeRuleMetadata:
    """Tests for rule identity and regulatory metadata."""

    def test_rule_id(self) -> None:
        assert IssueSizeRule().rule_id == "ISSUE_SIZE_5X"

    def test_category_is_mandatory(self) -> None:
        from app.models.enums import RuleCategory

        assert IssueSizeRule().category == RuleCategory.MANDATORY

    def test_regulation_references_sebi_icdr_26_2(self) -> None:
        meta = IssueSizeRule().metadata
        assert "26(2)" in meta.section
        assert "ICDR" in meta.regulation


class TestIssueSizeRulePass:
    """IssueSizeRule PASS scenarios."""

    def test_issue_size_well_below_5x_passes(self) -> None:
        """Default: issue=100, net_worth=50 → ratio 2x — passes comfortably."""
        company = CompanyDataFactory.create(
            issue_size=Decimal("100"),
            pre_issue_net_worth=Decimal("50"),
        )
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None
        assert result.rule_id == "ISSUE_SIZE_5X"

    def test_exactly_5x_boundary_passes(self) -> None:
        """Exactly 5× pre-issue net worth must pass (condition is <=, not <)."""
        company = CompanyDataFactory.create(
            issue_size=Decimal("250"),
            pre_issue_net_worth=Decimal("50"),
        )
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None

    def test_small_issue_large_net_worth_passes(self) -> None:
        """Issue size of Rs 1 Cr against Rs 100 Cr net worth is well within limit."""
        company = CompanyDataFactory.create(
            issue_size=Decimal("1"),
            pre_issue_net_worth=Decimal("100"),
        )
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_explanation_present_on_pass(self) -> None:
        company = CompanyDataFactory.create(
            issue_size=Decimal("50"),
            pre_issue_net_worth=Decimal("50"),
        )
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.explanation
        assert "5" in result.explanation


class TestIssueSizeRuleFail:
    """IssueSizeRule FAIL scenarios."""

    def test_issue_size_exceeds_5x(self) -> None:
        """Rs 300 Cr issue against Rs 50 Cr net worth = 6× — fails."""
        company = CompanyDataFactory.create(
            issue_size=Decimal("300"),
            pre_issue_net_worth=Decimal("50"),
        )
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_just_above_5x_fails(self) -> None:
        """Rs 250.01 Cr against Rs 50 Cr net worth is just above the limit."""
        company = CompanyDataFactory.create(
            issue_size=Decimal("250.01"),
            pre_issue_net_worth=Decimal("50"),
        )
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_zero_net_worth_fails(self) -> None:
        """Zero pre-issue net worth: ratio is undefined — auto FAIL."""
        company = CompanyDataFactory.create(
            issue_size=Decimal("100"),
            pre_issue_net_worth=Decimal("0"),
        )
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        # Gap should explain the non-positive net worth problem
        assert "≤ 0" in result.gap or "non-positive" in result.gap.lower() or "0" in result.gap

    def test_negative_net_worth_fails(self) -> None:
        """Negative pre-issue net worth: ratio undefined — auto FAIL."""
        company = CompanyDataFactory.create(
            issue_size=Decimal("100"),
            pre_issue_net_worth=Decimal("-10"),
        )
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_gap_contains_limit_and_actual(self) -> None:
        """Gap message must include the issue size and the 5× limit."""
        company = CompanyDataFactory.create(
            issue_size=Decimal("600"),
            pre_issue_net_worth=Decimal("100"),
        )
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        # Limit = 5 * 100 = 500 Cr; issue = 600 Cr
        assert "600" in result.gap
        assert "500" in result.gap


class TestIssueSizeRuleInconclusive:
    """IssueSizeRule INCONCLUSIVE scenarios."""

    def test_low_confidence_issue_size_inconclusive(self) -> None:
        """If issue_size ExtractedValue is unreliable, result must be INCONCLUSIVE.

        The factory produces HIGH-confidence (MANUAL) values, so we must
        construct the company data with an overridden LOW-confidence issue_size
        by passing a pre-built list of overrides through the factory's
        fiscal_years pathway. Instead, we patch the issue_details directly
        by reading from a low-confidence ExtractedValue injected via a custom
        CompanyData construction.
        """
        # We cannot directly set low-confidence on issue_size through the factory,
        # so we build the company normally then rebuild issue_details with low conf.
        from app.models.company_data import IssueDetails

        company_base = CompanyDataFactory.create(
            issue_size=Decimal("100"),
            pre_issue_net_worth=Decimal("50"),
        )
        low_conf_issue_size = _low_confidence_ev(Decimal("100"))
        new_issue_details = IssueDetails(
            issue_size=low_conf_issue_size,
            pre_issue_net_worth=company_base.issue_details.pre_issue_net_worth,
            post_issue_paid_up_capital=company_base.issue_details.post_issue_paid_up_capital,
            expected_market_cap=company_base.issue_details.expected_market_cap,
            public_offer_percentage=company_base.issue_details.public_offer_percentage,
            issue_type=company_base.issue_details.issue_type,
        )
        company = company_base.model_copy(update={"issue_details": new_issue_details})
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_pre_issue_net_worth_inconclusive(self) -> None:
        """If pre_issue_net_worth ExtractedValue is unreliable → INCONCLUSIVE."""
        from app.models.company_data import IssueDetails

        company_base = CompanyDataFactory.create(
            issue_size=Decimal("100"),
            pre_issue_net_worth=Decimal("50"),
        )
        low_conf_net_worth = _low_confidence_ev(Decimal("50"))
        new_issue_details = IssueDetails(
            issue_size=company_base.issue_details.issue_size,
            pre_issue_net_worth=low_conf_net_worth,
            post_issue_paid_up_capital=company_base.issue_details.post_issue_paid_up_capital,
            expected_market_cap=company_base.issue_details.expected_market_cap,
            public_offer_percentage=company_base.issue_details.public_offer_percentage,
            issue_type=company_base.issue_details.issue_type,
        )
        company = company_base.model_copy(update={"issue_details": new_issue_details})
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_inconclusive_explanation_present(self) -> None:
        """INCONCLUSIVE results must include a manual-review explanation."""
        from app.models.company_data import IssueDetails

        company_base = CompanyDataFactory.create()
        low_conf_issue_size = _low_confidence_ev(Decimal("100"))
        new_issue_details = IssueDetails(
            issue_size=low_conf_issue_size,
            pre_issue_net_worth=company_base.issue_details.pre_issue_net_worth,
            post_issue_paid_up_capital=company_base.issue_details.post_issue_paid_up_capital,
            expected_market_cap=company_base.issue_details.expected_market_cap,
            public_offer_percentage=company_base.issue_details.public_offer_percentage,
            issue_type=company_base.issue_details.issue_type,
        )
        company = company_base.model_copy(update={"issue_details": new_issue_details})
        result = IssueSizeRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.explanation
        assert "manual review" in result.explanation.lower()
