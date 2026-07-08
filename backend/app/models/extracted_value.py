"""
backend/app/models/extracted_value.py

Generic provenance wrapper for every extracted financial data point.

Every numeric, boolean, or string value that originates from a document
is wrapped in ExtractedValue[T]. The wrapper carries full provenance
metadata: where it came from, how it was obtained, and how confident
we are in the extraction.

This module MUST NOT import from:
  - app.rules, app.parser, app.api, app.engine

Design notes:
  - Generic[T] allows typed wrapping of Decimal, int, str, bool, etc.
  - frozen=True enforces immutability — extracted values are facts.
  - LOW confidence without human confirmation causes INCONCLUSIVE verdicts.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from app.models.enums import ConfidenceLevel, ExtractionMethod

T = TypeVar("T")


class ExtractedValue(BaseModel, Generic[T]):
    """Provenance-wrapped value extracted from a source document.

    Every financial data point in CompanyData is wrapped in this type.
    The wrapper is immutable after construction — extracted values are
    domain facts and must not be modified after the extraction pipeline
    produces them.

    A value with confidence=LOW and confirmed_by_human=False will cause
    any rule that reads it to return INCONCLUSIVE instead of PASS or FAIL.
    This is the system's mechanism for surfacing data quality problems
    without silently producing wrong eligibility verdicts.

    Attributes:
        value: The actual data value. Use Decimal for all financial figures.
        source_document: Name of the document this was extracted from,
            e.g., "Annual_Report_FY2024.pdf".
        page_number: Page in the source document, if known.
        extraction_method: How the value was obtained (PDF_TABLE, OCR,
            MANUAL, or AI_EXTRACTED).
        confidence: Confidence in the extracted value. See ConfidenceLevel.
        confirmed_by_human: True if a human has reviewed and confirmed this
            value. Required before a LOW confidence value can be used in
            a deterministic verdict.
        raw_text: Original text snippet from the document before parsing,
            for audit purposes.

    Example:
        >>> from decimal import Decimal
        >>> from app.models.enums import ConfidenceLevel, ExtractionMethod
        >>> ev = ExtractedValue(
        ...     value=Decimal("18.4"),
        ...     source_document="Annual_Report_FY2024.pdf",
        ...     page_number=143,
        ...     extraction_method=ExtractionMethod.PDF_TABLE,
        ...     confidence=ConfidenceLevel.HIGH,
        ...     confirmed_by_human=False,
        ... )
        >>> ev.value
        Decimal('18.4')
        >>> ev.confidence
        <ConfidenceLevel.HIGH: 'high'>
    """

    model_config = ConfigDict(frozen=True)

    value: T
    source_document: str
    page_number: int | None = None
    extraction_method: ExtractionMethod
    confidence: ConfidenceLevel
    confirmed_by_human: bool = False
    raw_text: str | None = None

    def is_reliable(self) -> bool:
        """Return True if this value can be used in a deterministic verdict.

        A value is reliable when its confidence is HIGH or MEDIUM, or when
        it has LOW confidence but a human has confirmed it. MANUAL entries
        are always considered reliable regardless of confidence level.

        Returns:
            True if the value may be used in rule evaluation without
            triggering an INCONCLUSIVE verdict.

        Example:
            >>> from decimal import Decimal
            >>> ev_high = ExtractedValue(
            ...     value=Decimal("5.0"),
            ...     source_document="doc.pdf",
            ...     extraction_method=ExtractionMethod.PDF_TABLE,
            ...     confidence=ConfidenceLevel.HIGH,
            ... )
            >>> ev_high.is_reliable()
            True
            >>> ev_low = ExtractedValue(
            ...     value=Decimal("5.0"),
            ...     source_document="doc.pdf",
            ...     extraction_method=ExtractionMethod.OCR,
            ...     confidence=ConfidenceLevel.LOW,
            ... )
            >>> ev_low.is_reliable()
            False
        """
        if self.extraction_method == ExtractionMethod.MANUAL:
            return True
        if self.confidence == ConfidenceLevel.LOW:
            return self.confirmed_by_human
        return True
