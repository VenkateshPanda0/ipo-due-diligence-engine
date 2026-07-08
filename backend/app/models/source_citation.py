"""
backend/app/models/source_citation.py

SourceCitation model for evidence traceability.

Every RuleResult carries a SourceCitation that links the verdict back to
specific pages and tables in the source document. This is the first link
in the four-link evidence chain described in ARCHITECTURE.md §11.

This module MUST NOT import from:
  - app.rules, app.parser, app.api, app.engine
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.enums import ConfidenceLevel, ExtractionMethod
from app.models.extracted_value import ExtractedValue

type CitationExtractedValue = (
    ExtractedValue[bool] | ExtractedValue[int] | ExtractedValue[Decimal] | ExtractedValue[str]
)


class SourceCitation(BaseModel):
    """Links a rule verdict back to its evidence in the source document.

    The SourceCitation is attached to every RuleResult by the Evidence Mapper.
    It provides the full provenance chain required by auditors and investment
    bankers: which document, which page, which table, which value, extracted
    how, and with what confidence.

    The overall confidence of a citation is the lowest confidence among all
    extracted values it references — the weakest link in the evidence chain.

    Attributes:
        document_name: Name of the source document, e.g.,
            "Annual_Report_FY2024.pdf".
        page_numbers: List of page numbers where the evidence appears.
        table_reference: Human-readable table identifier, e.g.,
            "Statement of Profit and Loss, Table 3".
        extracted_values: All ExtractedValue objects used in evaluating
            the associated rule. Preserves full provenance for each value.
        extraction_method: Dominant extraction method used for this citation.
        confidence: Lowest confidence among all extracted_values. Represents
            the weakest link in the evidence chain.
        raw_snippets: Original text snippets from the document, for audit.

    Example:
        >>> from decimal import Decimal
        >>> from app.models.enums import ConfidenceLevel, ExtractionMethod
        >>> ev = ExtractedValue(
        ...     value=Decimal("18.4"),
        ...     source_document="Annual_Report_FY2024.pdf",
        ...     page_number=47,
        ...     extraction_method=ExtractionMethod.PDF_TABLE,
        ...     confidence=ConfidenceLevel.HIGH,
        ... )
        >>> citation = SourceCitation(
        ...     document_name="Annual_Report_FY2024.pdf",
        ...     page_numbers=[47],
        ...     table_reference="Statement of Profit and Loss",
        ...     extracted_values=[ev],
        ...     extraction_method=ExtractionMethod.PDF_TABLE,
        ...     confidence=ConfidenceLevel.HIGH,
        ... )
        >>> citation.confidence
        <ConfidenceLevel.HIGH: 'high'>
    """

    model_config = ConfigDict(frozen=True)

    document_name: str
    page_numbers: list[int]
    table_reference: str | None = None
    extracted_values: list[CitationExtractedValue]
    extraction_method: ExtractionMethod
    confidence: ConfidenceLevel
    raw_snippets: list[str] | None = None

    @field_validator("extracted_values", mode="before")
    @classmethod
    def restore_extracted_value_types(cls, value: Any) -> Any:
        """Restore concrete ExtractedValue generics from JSON payloads."""
        if not isinstance(value, list):
            return value
        restored: list[CitationExtractedValue] = []
        for item in value:
            if not isinstance(item, dict) or "value" not in item:
                restored.append(cast("CitationExtractedValue", item))
                continue
            raw_value = item["value"]
            if isinstance(raw_value, bool):
                restored.append(ExtractedValue[bool].model_validate(item))
            elif isinstance(raw_value, int):
                restored.append(ExtractedValue[int].model_validate(item))
            elif isinstance(raw_value, str):
                try:
                    Decimal(raw_value)
                except Exception:
                    restored.append(ExtractedValue[str].model_validate(item))
                else:
                    restored.append(ExtractedValue[Decimal].model_validate(item))
            else:
                restored.append(ExtractedValue[Decimal].model_validate(item))
        return restored

    @model_validator(mode="after")
    def derive_confidence_from_values(self) -> SourceCitation:
        """Ensure confidence reflects the weakest extracted value.

        The system uses the lowest confidence level among all extracted
        values as the citation's overall confidence. If extracted_values
        is empty, the explicitly provided confidence is used as-is.

        Returns:
            The validated SourceCitation instance.
        """
        if not self.extracted_values:
            return self

        confidence_rank = {
            ConfidenceLevel.HIGH: 2,
            ConfidenceLevel.MEDIUM: 1,
            ConfidenceLevel.LOW: 0,
        }
        min_confidence = min(
            self.extracted_values,
            key=lambda ev: confidence_rank[ev.confidence],
        ).confidence

        # We use object.__setattr__ because the model is frozen.
        object.__setattr__(self, "confidence", min_confidence)
        return self
