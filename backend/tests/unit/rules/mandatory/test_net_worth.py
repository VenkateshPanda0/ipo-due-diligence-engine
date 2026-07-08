"""
backend/tests/unit/rules/mandatory/test_net_worth.py

Unit tests for NET_WORTH_1CR mandatory rule (SEBI ICDR Regulation 26(1)(c)).

100% branch coverage for NetWorthRule.evaluate():
  - PASS: all 3 years >= Rs 1 Cr
  - PASS: exactly Rs 1 Cr boundary in all 3 years
  - FAIL: one year below threshold
  - FAIL: all 3 years below threshold
  - FAIL: negative net worth
  - FAIL: gap identifies worst shortfall year
  - INCONCLUSIVE: fewer than 3 fiscal years available
  - INCONCLUSIVE: zero fiscal years (empty list branch)
  - INCONCLUSIVE: net_worth has LOW confidence without human confirmation
"""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import ConfidenceLevel, Verdict
from app.rules.mandatory.net_worth import NetWorthRule
from tests.fixtures.company_data_factory import CompanyDataFactory, _make_fiscal_year


class TestNetWorthRuleMetadata:
    """Tests for rule identity and regulatory metadata."""

    def test_rule_id(self) -> None:
        assert NetWorthRule().rule_id == "NET_WORTH_1CR"

    def test_category_is_mandatory(self) -> None:
        from app.models.enums import RuleCategory

        assert NetWorthRule().category == RuleCategory.MANDATORY

    def test_regulation_references_sebi_icdr(self) -> None:
        meta = NetWorthRule().metadata
        assert "26(1)" in meta.section
        assert "ICDR" in meta.regulation

    def test_clause_references_c(self) -> None:
        meta = NetWorthRule().metadata
        assert meta.clause is not None
        assert "(c)" in meta.clause


class TestNetWorthRulePass:
    """NetWorthRule PASS scenarios."""

    def test_all_years_clearly_above_1cr(self) -> None:
        """Default factory uses Rs 50 Cr net worth — well above threshold."""
        company = CompanyDataFactory.create(net_worth=Decimal("50"))
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None
        assert result.rule_id == "NET_WORTH_1CR"

    def test_exactly_1cr_boundary_passes(self) -> None:
        """Net worth of exactly Rs 1 Cr must pass (>= threshold, not >)."""
        company = CompanyDataFactory.create(net_worth=Decimal("1"))
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.gap is None

    def test_uses_last_3_of_5_fiscal_years(self) -> None:
        """With 5 years, only the 3 most recent are checked.

        Old years with low net worth should be ignored when the last 3 pass.
        """
        years = [
            _make_fiscal_year("FY2020", net_worth=Decimal("0.5")),  # old – ignored
            _make_fiscal_year("FY2021", net_worth=Decimal("0.2")),  # old – ignored
            _make_fiscal_year("FY2022", net_worth=Decimal("5")),
            _make_fiscal_year("FY2023", net_worth=Decimal("6")),
            _make_fiscal_year("FY2024", net_worth=Decimal("7")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_explanation_present_on_pass(self) -> None:
        company = CompanyDataFactory.create(net_worth=Decimal("10"))
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.PASS
        assert result.explanation
        assert "₹1 Crore" in result.explanation or "₹1 Cr" in result.explanation


class TestNetWorthRuleFail:
    """NetWorthRule FAIL scenarios."""

    def test_one_year_below_1cr(self) -> None:
        """Single year below threshold causes FAIL."""
        years = [
            _make_fiscal_year("FY2022", net_worth=Decimal("5")),
            _make_fiscal_year("FY2023", net_worth=Decimal("0.5")),  # below Rs 1 Cr
            _make_fiscal_year("FY2024", net_worth=Decimal("5")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        assert "FY2023" in result.gap

    def test_all_years_below_1cr(self) -> None:
        """All three years below the Rs 1 Cr threshold."""
        company = CompanyDataFactory.create(net_worth=Decimal("0.5"))
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_just_below_threshold_fails(self) -> None:
        """Rs 0.99 Cr is strictly below Rs 1 Cr and must fail."""
        company = CompanyDataFactory.create(net_worth=Decimal("0.99"))
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_negative_net_worth_fails(self) -> None:
        """Negative net worth is an automatic failure."""
        company = CompanyDataFactory.create(net_worth=Decimal("-10"))
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None

    def test_gap_identifies_worst_shortfall_year(self) -> None:
        """Gap message should reference the year with the smallest (worst) net worth."""
        years = [
            _make_fiscal_year("FY2022", net_worth=Decimal("0.8")),
            _make_fiscal_year("FY2023", net_worth=Decimal("0.3")),  # worst
            _make_fiscal_year("FY2024", net_worth=Decimal("0.6")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        # Worst shortfall is FY2023 with Rs 0.3 Cr (shortfall Rs 0.7 Cr)
        assert "FY2023" in result.gap

    def test_gap_message_contains_shortfall_amount(self) -> None:
        """Gap must contain the quantified shortfall below the Rs 1 Cr floor."""
        years = [
            _make_fiscal_year("FY2022", net_worth=Decimal("5")),
            _make_fiscal_year("FY2023", net_worth=Decimal("0.4")),
            _make_fiscal_year("FY2024", net_worth=Decimal("5")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.FAIL
        assert result.gap is not None
        # Shortfall = 1 - 0.4 = 0.60
        assert "0.60" in result.gap


class TestNetWorthRuleInconclusive:
    """NetWorthRule INCONCLUSIVE scenarios."""

    def test_only_2_years_inconclusive(self) -> None:
        """Fewer than 3 years of data must yield INCONCLUSIVE."""
        years = [
            _make_fiscal_year("FY2023", net_worth=Decimal("5")),
            _make_fiscal_year("FY2024", net_worth=Decimal("5")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years, years_of_operation=2)
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_only_1_year_inconclusive(self) -> None:
        """A single fiscal year is insufficient."""
        years = [_make_fiscal_year("FY2024", net_worth=Decimal("5"))]
        company = CompanyDataFactory.create(fiscal_years=years, years_of_operation=1)
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_zero_years_inconclusive(self) -> None:
        """Empty fiscal_years list exercises the 'no fiscal year data' branch."""
        company = CompanyDataFactory.create(fiscal_years=[], years_of_operation=0)
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.explanation
        # Covers the 'else' branch: actual_value = "no fiscal year data"
        assert "no fiscal year" in result.explanation.lower() or "0" in result.explanation

    def test_low_confidence_net_worth_inconclusive(self) -> None:
        """LOW-confidence net_worth without human confirmation → INCONCLUSIVE."""
        years = [
            _make_fiscal_year("FY2022", net_worth=Decimal("5"), confidence=ConfidenceLevel.LOW),
            _make_fiscal_year("FY2023", net_worth=Decimal("5")),
            _make_fiscal_year("FY2024", net_worth=Decimal("5")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_low_confidence_in_middle_year_inconclusive(self) -> None:
        """LOW confidence in any of the last-3 years triggers INCONCLUSIVE."""
        years = [
            _make_fiscal_year("FY2022", net_worth=Decimal("5")),
            _make_fiscal_year("FY2023", net_worth=Decimal("5"), confidence=ConfidenceLevel.LOW),
            _make_fiscal_year("FY2024", net_worth=Decimal("5")),
        ]
        company = CompanyDataFactory.create(fiscal_years=years)
        result = NetWorthRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_explanation_present_on_inconclusive(self) -> None:
        years = [_make_fiscal_year("FY2024", net_worth=Decimal("5"))]
        company = CompanyDataFactory.create(fiscal_years=years, years_of_operation=1)
        result = NetWorthRule().evaluate(company)
        assert result.explanation
        assert "manual review" in result.explanation.lower()
