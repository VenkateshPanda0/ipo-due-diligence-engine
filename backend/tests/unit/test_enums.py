"""
backend/tests/unit/test_enums.py

Unit tests for domain enumerations (M2-023).

Verifies that all enum values exist, have correct string representations,
and are serialisable to/from JSON as expected.
"""

from __future__ import annotations

import pytest

from app.models.enums import (
    ConfidenceLevel,
    ExtractionMethod,
    IPOStatus,
    RuleCategory,
    Verdict,
)


class TestIPOStatus:
    """Tests for IPOStatus enum."""

    def test_all_values_present(self) -> None:
        """All three status values must be defined."""
        assert IPOStatus.ELIGIBLE.value == "eligible"
        assert IPOStatus.NOT_ELIGIBLE.value == "not_eligible"
        assert IPOStatus.NEEDS_REVIEW.value == "needs_review"

    def test_exhaustive_coverage(self) -> None:
        """Enum has exactly 3 members."""
        assert len(IPOStatus) == 3

    def test_string_subclass(self) -> None:
        """IPOStatus is a str subclass for JSON serialisation."""
        assert isinstance(IPOStatus.ELIGIBLE, str)
        assert IPOStatus.ELIGIBLE == "eligible"

    def test_from_value(self) -> None:
        """Can reconstruct enum from string value."""
        assert IPOStatus("not_eligible") == IPOStatus.NOT_ELIGIBLE


class TestVerdict:
    """Tests for Verdict enum."""

    def test_all_values_present(self) -> None:
        assert Verdict.PASS.value == "pass"
        assert Verdict.FAIL.value == "fail"
        assert Verdict.INCONCLUSIVE.value == "inconclusive"

    def test_exhaustive_coverage(self) -> None:
        assert len(Verdict) == 5
        assert Verdict.REQUIRES_HUMAN_REVIEW.value == "requires_human_review"
        assert Verdict.NOT_APPLICABLE.value == "not_applicable"

    def test_string_subclass(self) -> None:
        assert isinstance(Verdict.PASS, str)
        assert Verdict.FAIL == "fail"

    def test_from_value(self) -> None:
        assert Verdict("pass") == Verdict.PASS
        assert Verdict("inconclusive") == Verdict.INCONCLUSIVE


class TestRuleCategory:
    """Tests for RuleCategory enum."""

    def test_all_values_present(self) -> None:
        assert RuleCategory.MANDATORY.value == "mandatory"
        assert RuleCategory.ADVISORY.value == "advisory"

    def test_exhaustive_coverage(self) -> None:
        assert len(RuleCategory) == 2

    def test_string_subclass(self) -> None:
        assert isinstance(RuleCategory.MANDATORY, str)

    def test_from_value(self) -> None:
        assert RuleCategory("advisory") == RuleCategory.ADVISORY


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_all_values_present(self) -> None:
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"

    def test_exhaustive_coverage(self) -> None:
        assert len(ConfidenceLevel) == 3

    def test_string_subclass(self) -> None:
        assert isinstance(ConfidenceLevel.HIGH, str)
        assert ConfidenceLevel.LOW == "low"

    def test_from_value(self) -> None:
        assert ConfidenceLevel("medium") == ConfidenceLevel.MEDIUM


class TestExtractionMethod:
    """Tests for ExtractionMethod enum."""

    def test_all_values_present(self) -> None:
        assert ExtractionMethod.PDF_TABLE.value == "pdf_table"
        assert ExtractionMethod.OCR.value == "ocr"
        assert ExtractionMethod.MANUAL.value == "manual"
        assert ExtractionMethod.AI_EXTRACTED.value == "ai_extracted"

    def test_exhaustive_coverage(self) -> None:
        assert len(ExtractionMethod) == 7

    def test_string_subclass(self) -> None:
        assert isinstance(ExtractionMethod.MANUAL, str)
        assert ExtractionMethod.OCR == "ocr"

    def test_from_value(self) -> None:
        assert ExtractionMethod("pdf_table") == ExtractionMethod.PDF_TABLE
        assert ExtractionMethod("ai_extracted") == ExtractionMethod.AI_EXTRACTED

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            ExtractionMethod("invalid_method")
