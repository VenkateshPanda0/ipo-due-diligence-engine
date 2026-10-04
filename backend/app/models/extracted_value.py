"""
backend/app/models/extracted_value.py

Generic provenance wrapper for every fact used by the rules engine.

The normalised business value (``value``) is kept separate from its source
representation (``original_text``/``original_unit``) and provenance. Values are
immutable; a human correction produces a new ExtractedValue and an append-only
correction event elsewhere — the original is never overwritten.

This module MUST NOT import from app.rules, app.intelligence, app.api, app.engine.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ConfidenceLevel, ExtractionMethod, FieldStatus, StatementBasis

T = TypeVar("T")

_NEEDS_CONFIRMATION = frozenset(
    {FieldStatus.CONFLICTING_CANDIDATES, FieldStatus.EXTRACTED_NEEDS_VERIFICATION}
)


class ExtractedValue(BaseModel, Generic[T]):
    """Provenance-wrapped value.

    Attributes:
        value: Normalised value. Monetary values are Decimal ₹ crore.
        source_document: Document name (or "manual entry").
        page_number: 1-based page in the source document, if known.
        extraction_method: How the value was obtained.
        confidence: Extraction confidence (not a legal confidence).
        confirmed_by_human: A reviewer confirmed this value.
        raw_text: Source snippet (row/line context) for audit.
        unit: Canonical unit of ``value`` (e.g. ``INR_CRORE``, ``PERCENT``).
        original_text: Exact token as printed, e.g. ``"(1,234.50)"``.
        original_unit: Unit as declared in the source, e.g. ``INR_LAKH``.
        period_label: Reporting period the value belongs to.
        statement_basis: Consolidated / standalone / unknown.
        field_status: Field-level extraction status.
        conflicting_values: Other candidate values found for the same field.
        notes: Normalisation and validation notes.
        document_id: Stable document identifier (SHA-256) when known.
    """

    model_config = ConfigDict(frozen=True)

    value: T
    source_document: str
    page_number: int | None = None
    extraction_method: ExtractionMethod
    confidence: ConfidenceLevel
    confirmed_by_human: bool = False
    raw_text: str | None = None
    unit: str | None = None
    original_text: str | None = None
    original_unit: str | None = None
    period_label: str | None = None
    statement_basis: StatementBasis | None = None
    field_status: FieldStatus | None = None
    conflicting_values: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    document_id: str | None = None

    def is_reliable(self) -> bool:
        """Return True if the value may be used for a PASS/FAIL determination.

        MANUAL entries and human-confirmed values are reliable. Otherwise a
        value is unreliable if it is LOW confidence or flagged as conflicting /
        needing verification.
        """
        if self.confirmed_by_human:
            return True
        if self.extraction_method in (ExtractionMethod.MANUAL, ExtractionMethod.HUMAN_CORRECTED):
            return True
        if self.field_status in _NEEDS_CONFIRMATION:
            return False
        return self.confidence != ConfidenceLevel.LOW

    def review_reason(self) -> str:
        """Explain why the value is not reliable (empty string if reliable)."""
        if self.is_reliable():
            return ""
        if self.field_status == FieldStatus.CONFLICTING_CANDIDATES:
            others = ", ".join(self.conflicting_values) or "other candidates"
            return f"conflicting candidates ({others})"
        if self.field_status == FieldStatus.EXTRACTED_NEEDS_VERIFICATION:
            return "extracted value requires verification"
        return "low extraction confidence without human confirmation"
