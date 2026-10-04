"""
backend/app/models/evidence.py

Evidence references attached to rule results.

An EvidenceRef is a flattened, serialisable copy of the provenance of one input
fact used by a rule (or of a value the rule calculated). ``kind`` distinguishes
directly extracted values, manual entries, reviewer corrections and calculations
so the UI never presents a calculation as a quoted document value.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    ConfidenceLevel,
    ExtractionMethod,
    FieldStatus,
    StatementBasis,
)
from app.models.extracted_value import ExtractedValue


class EvidenceRef(BaseModel):
    """One fact a rule relied on, with provenance."""

    model_config = ConfigDict(frozen=True)

    field_path: str
    value: str
    unit: str | None = None
    kind: str  # "extracted" | "manual" | "reviewer" | "calculated"
    source_document: str | None = None
    document_id: str | None = None
    page_number: int | None = None
    extraction_method: ExtractionMethod | None = None
    confidence: ConfidenceLevel | None = None
    confirmed_by_human: bool = False
    field_status: FieldStatus | None = None
    raw_text: str | None = None
    original_text: str | None = None
    original_unit: str | None = None
    period_label: str | None = None
    statement_basis: StatementBasis | None = None
    reliable: bool = True

    @classmethod
    def from_extracted(cls, field_path: str, ev: ExtractedValue[Any]) -> EvidenceRef:
        """Build from an ExtractedValue."""
        if ev.extraction_method == ExtractionMethod.MANUAL:
            kind = "manual"
        elif ev.extraction_method == ExtractionMethod.HUMAN_CORRECTED or ev.confirmed_by_human:
            kind = "reviewer"
        elif ev.extraction_method == ExtractionMethod.CALCULATED:
            kind = "calculated"
        else:
            kind = "extracted"
        return cls(
            field_path=field_path,
            value=str(ev.value),
            unit=ev.unit,
            kind=kind,
            source_document=ev.source_document,
            document_id=ev.document_id,
            page_number=ev.page_number,
            extraction_method=ev.extraction_method,
            confidence=ev.confidence,
            confirmed_by_human=ev.confirmed_by_human,
            field_status=ev.field_status,
            raw_text=ev.raw_text,
            original_text=ev.original_text,
            original_unit=ev.original_unit,
            period_label=ev.period_label,
            statement_basis=ev.statement_basis,
            reliable=ev.is_reliable(),
        )

    @classmethod
    def calculated(cls, field_path: str, value: str, unit: str | None = None) -> EvidenceRef:
        """Build a reference for a value computed by the rule."""
        return cls(field_path=field_path, value=value, unit=unit, kind="calculated")
