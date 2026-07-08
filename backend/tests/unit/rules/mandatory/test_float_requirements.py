"""
backend/tests/unit/rules/mandatory/test_float_requirements.py

Unit tests for PUBLIC_OFFER_MIN mandatory rule (SEBI ICDR Regulation 26(5)).

100% branch coverage for FloatRequirementsRule.evaluate():
  - INCONCLUSIVE: expected_market_cap has LOW confidence
  - INCONCLUSIVE: public_offer_percentage has LOW confidence
  - PASS (small-cap tier): market cap <= Rs 1600 Cr and offer >= 25%
  - PASS (large-cap tier): market cap > Rs 1600 Cr and offer >= 10%
  - FAIL (small-cap tier): offer < 25%
  - FAIL (large-cap tier): offer < 10%
  - PASS: exactly Rs 1600 Cr boundary uses the small-cap threshold (25%)
  - PASS: exactly 25% float for small-cap (boundary)
  - PASS: exactly 10% float for large-cap (boundary)
  - Gap calculation verified
"""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import ConfidenceLevel, ExtractionMethod, Verdict
from app.models.extracted_value import ExtractedValue
from app.rules.mandatory.float_requirements import FloatRequirementsRule
from tests.fixtures.company_data_factory import CompanyDataFactory


def _low_confidence_ev(value: Decimal) -> ExtractedValue[Decimal]:
    """Build a LOW-confidence OCR-extracted ExtractedValue (unreliable)."""
    return ExtractedValue(
        value=value,
        source_document="scanned_drhp.pdf",
        page_number=1,
        extraction_method=ExtractionMethod.OCR,
        confidence=ConfidenceLevel.LOW,
        confirmed_by_human=False,
    )


class TestFloatRequirementsRuleMetadata:
    """Tests for rule identity and regulatory metadata."""

    def test_rule_id(self) -> None:
        assert FloatRequirementsRule().rule_id == "PUBLIC_OFFER_MIN"

    def test_category_is_mandatory(self) -> None:
        from app.models.enums import RuleCategory

        assert FloatRequirementsRule().category == RuleCategory.MANDATORY

    def test_regulation_references_sebi_icdr_26_5(self) -> None:
        meta = FloatRequirementsRule().metadata
        assert "26(5)" in meta.section
        assert "ICDR" in meta.regulation


class TestFloatRequirementsRulePassSmallCap:
    """PUBLIC_OFFER_MIN PASS for small-cap tier (market cap <= Rs 1600 Cr)."""

    def test_25_pct_float_for_800cr_market_cap_passes(self) -> None:
        """Default factory: Rs 800 Cr market cap, 25% offer — passes."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("800"),
            public_offer_percentage=Decimal("25"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None
        assert result.rule_id == "PUBLIC_OFFER_MIN"

    def test_exactly_25_pct_boundary_small_cap_passes(self) -> None:
        """Exactly 25% for small-cap is at the boundary (>= 25%)."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("1000"),
            public_offer_percentage=Decimal("25"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_more_than_25_pct_small_cap_passes(self) -> None:
        """40% public offer with Rs 500 Cr market cap passes."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("500"),
            public_offer_percentage=Decimal("40"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None

    def test_exactly_1600cr_market_cap_uses_small_cap_threshold(self) -> None:
        """The 1600 Cr boundary uses the small-cap threshold (<= 1600).

        At Rs 1600 Cr exactly, minimum float is 25% (not 10%).
        """
        # With 25% offer, should PASS (using 25% threshold)
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("1600"),
            public_offer_percentage=Decimal("25"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_exactly_1600cr_with_only_10_pct_fails(self) -> None:
        """At Rs 1600 Cr exactly, 10% float is insufficient (threshold is 25%)."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("1600"),
            public_offer_percentage=Decimal("10"),
        )
        result = FloatRequirementsRule().evaluate(company)
        # 1600 is <= 1600, so threshold is 25%; 10% < 25% => FAIL
        assert result.verdict == Verdict.FAIL


class TestFloatRequirementsRulePassLargeCap:
    """PUBLIC_OFFER_MIN PASS for large-cap tier (market cap > Rs 1600 Cr)."""

    def test_10_pct_float_for_2000cr_market_cap_passes(self) -> None:
        """Rs 2000 Cr market cap with 10% offer passes."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("2000"),
            public_offer_percentage=Decimal("10"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None

    def test_exactly_10_pct_boundary_large_cap_passes(self) -> None:
        """Exactly 10% for large-cap is at the boundary (>= 10%)."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("5000"),
            public_offer_percentage=Decimal("10"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_above_1600cr_triggers_large_cap_tier(self) -> None:
        """Rs 1601 Cr (just above threshold) requires only 10% float."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("1601"),
            public_offer_percentage=Decimal("10"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_more_than_10_pct_large_cap_passes(self) -> None:
        """15% offer for Rs 3000 Cr market cap passes."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("3000"),
            public_offer_percentage=Decimal("15"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.PASS


class TestFloatRequirementsRuleFail:
    """PUBLIC_OFFER_MIN FAIL scenarios."""

    def test_low_float_small_cap_fails(self) -> None:
        """Rs 800 Cr market cap with only 20% offer — below 25% threshold."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("800"),
            public_offer_percentage=Decimal("20"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_just_below_25_pct_small_cap_fails(self) -> None:
        """24.99% for small-cap is strictly below 25%."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("1000"),
            public_offer_percentage=Decimal("24.99"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_low_float_large_cap_fails(self) -> None:
        """Rs 5000 Cr market cap with only 8% offer — below 10% threshold."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("5000"),
            public_offer_percentage=Decimal("8"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_just_below_10_pct_large_cap_fails(self) -> None:
        """9.99% for large-cap is strictly below 10%."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("2000"),
            public_offer_percentage=Decimal("9.99"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_gap_contains_shortfall_and_threshold(self) -> None:
        """Gap message must identify the offered % and the required minimum."""
        company = CompanyDataFactory.create(
            expected_market_cap=Decimal("800"),
            public_offer_percentage=Decimal("20"),
        )
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        # Threshold for small-cap is 25%; offered is 20%
        assert "20" in result.gap or "20.0" in result.gap
        assert "25" in result.gap


class TestFloatRequirementsRuleInconclusive:
    """PUBLIC_OFFER_MIN INCONCLUSIVE scenarios."""

    def test_low_confidence_market_cap_inconclusive(self) -> None:
        """Unreliable expected_market_cap → INCONCLUSIVE."""
        from app.models.company_data import IssueDetails

        company_base = CompanyDataFactory.create(
            expected_market_cap=Decimal("800"),
            public_offer_percentage=Decimal("25"),
        )
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
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_offer_pct_inconclusive(self) -> None:
        """Unreliable public_offer_percentage → INCONCLUSIVE."""
        from app.models.company_data import IssueDetails

        company_base = CompanyDataFactory.create(
            expected_market_cap=Decimal("800"),
            public_offer_percentage=Decimal("25"),
        )
        low_conf_offer_pct = _low_confidence_ev(Decimal("25"))
        new_issue_details = IssueDetails(
            issue_size=company_base.issue_details.issue_size,
            pre_issue_net_worth=company_base.issue_details.pre_issue_net_worth,
            post_issue_paid_up_capital=company_base.issue_details.post_issue_paid_up_capital,
            expected_market_cap=company_base.issue_details.expected_market_cap,
            public_offer_percentage=low_conf_offer_pct,
            issue_type=company_base.issue_details.issue_type,
        )
        company = company_base.model_copy(update={"issue_details": new_issue_details})
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_inconclusive_explanation_contains_manual_review(self) -> None:
        """INCONCLUSIVE verdict must request manual review."""
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
        result = FloatRequirementsRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.explanation
        assert "manual review" in result.explanation.lower()
