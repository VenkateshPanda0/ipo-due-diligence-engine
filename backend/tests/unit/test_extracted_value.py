"""
backend/tests/unit/test_extracted_value.py

Unit tests for ExtractedValue[T] generic (M2-024).

Tests: generic instantiation with Decimal/str/int/bool, immutability,
JSON round-trip, is_reliable() semantics for all confidence × extraction
method combinations.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.enums import ConfidenceLevel, ExtractionMethod
from app.models.extracted_value import ExtractedValue


def _ev(
    value: object,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    method: ExtractionMethod = ExtractionMethod.PDF_TABLE,
    confirmed: bool = False,
) -> ExtractedValue[object]:
    return ExtractedValue(
        value=value,
        source_document="test.pdf",
        page_number=1,
        extraction_method=method,
        confidence=confidence,
        confirmed_by_human=confirmed,
    )


class TestGenericInstantiation:
    """ExtractedValue works with various type parameters."""

    def test_decimal_value(self) -> None:
        ev = _ev(Decimal("18.4"))
        assert ev.value == Decimal("18.4")

    def test_int_value(self) -> None:
        ev = _ev(42)
        assert ev.value == 42

    def test_str_value(self) -> None:
        ev = _ev("some text")
        assert ev.value == "some text"

    def test_bool_value(self) -> None:
        ev = _ev(True)
        assert ev.value is True
        ev_false = _ev(False)
        assert ev_false.value is False

    def test_page_number_optional(self) -> None:
        ev = ExtractedValue(
            value=Decimal("5"),
            source_document="doc.pdf",
            extraction_method=ExtractionMethod.MANUAL,
            confidence=ConfidenceLevel.HIGH,
        )
        assert ev.page_number is None

    def test_raw_text_optional(self) -> None:
        ev = _ev(Decimal("10"))
        assert ev.raw_text is None

    def test_raw_text_set(self) -> None:
        ev = ExtractedValue(
            value=Decimal("10"),
            source_document="doc.pdf",
            extraction_method=ExtractionMethod.OCR,
            confidence=ConfidenceLevel.MEDIUM,
            raw_text="Revenue ₹10 Cr",
        )
        assert ev.raw_text == "Revenue ₹10 Cr"


class TestImmutability:
    """ExtractedValue is frozen after construction."""

    def test_assignment_raises(self) -> None:
        ev = _ev(Decimal("5"))
        with pytest.raises(ValidationError):
            ev.value = Decimal("999")  # type: ignore[misc]

    def test_attribute_deletion_raises(self) -> None:
        ev = _ev(Decimal("5"))
        with pytest.raises(ValidationError):
            del ev.value  # type: ignore[misc]


class TestIsReliable:
    """is_reliable() returns correct boolean for all combinations."""

    def test_high_confidence_pdf_table_reliable(self) -> None:
        ev = _ev(Decimal("5"), ConfidenceLevel.HIGH, ExtractionMethod.PDF_TABLE)
        assert ev.is_reliable() is True

    def test_medium_confidence_reliable(self) -> None:
        ev = _ev(Decimal("5"), ConfidenceLevel.MEDIUM, ExtractionMethod.AI_EXTRACTED)
        assert ev.is_reliable() is True

    def test_low_confidence_not_confirmed_unreliable(self) -> None:
        ev = _ev(Decimal("5"), ConfidenceLevel.LOW, ExtractionMethod.OCR, confirmed=False)
        assert ev.is_reliable() is False

    def test_low_confidence_confirmed_reliable(self) -> None:
        ev = _ev(Decimal("5"), ConfidenceLevel.LOW, ExtractionMethod.OCR, confirmed=True)
        assert ev.is_reliable() is True

    def test_manual_always_reliable_regardless_of_confidence(self) -> None:
        ev_low = _ev(Decimal("5"), ConfidenceLevel.LOW, ExtractionMethod.MANUAL, confirmed=False)
        assert ev_low.is_reliable() is True

        ev_high = _ev(Decimal("5"), ConfidenceLevel.HIGH, ExtractionMethod.MANUAL)
        assert ev_high.is_reliable() is True

    def test_high_confidence_ocr_reliable(self) -> None:
        ev = _ev(Decimal("5"), ConfidenceLevel.HIGH, ExtractionMethod.OCR)
        assert ev.is_reliable() is True


class TestJSONRoundTrip:
    """ExtractedValue serialises to JSON and back correctly."""

    def test_decimal_round_trip(self) -> None:
        ev = ExtractedValue(
            value=Decimal("18.4"),
            source_document="AR.pdf",
            page_number=143,
            extraction_method=ExtractionMethod.PDF_TABLE,
            confidence=ConfidenceLevel.HIGH,
        )
        data = ev.model_dump()
        assert data["value"] == Decimal("18.4")
        assert data["source_document"] == "AR.pdf"
        assert data["page_number"] == 143
        assert data["extraction_method"] == "pdf_table"
        assert data["confidence"] == "high"

    def test_json_serialisation(self) -> None:
        ev = ExtractedValue(
            value=Decimal("5.0"),
            source_document="doc.pdf",
            extraction_method=ExtractionMethod.MANUAL,
            confidence=ConfidenceLevel.HIGH,
        )
        json_str = ev.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["confidence"] == "high"
        assert parsed["extraction_method"] == "manual"

    def test_bool_serialises_correctly(self) -> None:
        ev = ExtractedValue(
            value=True,
            source_document="doc.pdf",
            extraction_method=ExtractionMethod.MANUAL,
            confidence=ConfidenceLevel.HIGH,
        )
        data = ev.model_dump()
        assert data["value"] is True
