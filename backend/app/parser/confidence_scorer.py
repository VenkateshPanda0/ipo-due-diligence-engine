"""Confidence scoring for extracted document values."""

from __future__ import annotations

from app.models.enums import ConfidenceLevel, ExtractionMethod


class ConfidenceScorer:
    """Assign confidence levels based on extraction method and corroboration."""

    def score(
        self,
        method: ExtractionMethod,
        *,
        corroborated: bool = False,
        source_count: int = 1,
        text_quality_usable: bool = True,
    ) -> ConfidenceLevel:
        """Return HIGH/MEDIUM/LOW confidence for an extraction path."""
        if method == ExtractionMethod.MANUAL:
            return ConfidenceLevel.HIGH
        if method == ExtractionMethod.PDF_TABLE and (corroborated or source_count >= 2):
            return ConfidenceLevel.HIGH
        if method == ExtractionMethod.PDF_TABLE and text_quality_usable:
            return ConfidenceLevel.MEDIUM
        if method == ExtractionMethod.AI_EXTRACTED and (corroborated or source_count >= 2):
            return ConfidenceLevel.MEDIUM
        if method == ExtractionMethod.OCR and corroborated and text_quality_usable:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
