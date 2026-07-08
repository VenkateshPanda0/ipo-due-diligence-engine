"""Heuristic document classifier for uploaded IPO diligence documents."""

from __future__ import annotations

from enum import StrEnum


class DocumentType(StrEnum):
    """Supported document types."""

    ANNUAL_REPORT = "annual_report"
    DRHP = "drhp"
    FINANCIAL_STATEMENT = "financial_statement"
    UNKNOWN = "unknown"


class DocumentClassifier:
    """Classify document text using deterministic heuristics."""

    def classify(self, text: str) -> DocumentType:
        """Classify a document from extracted text."""
        normalized = " ".join(text.lower().split())
        if any(
            phrase in normalized
            for phrase in (
                "draft red herring prospectus",
                "red herring prospectus",
                "drhp",
            )
        ):
            return DocumentType.DRHP
        if any(
            phrase in normalized
            for phrase in (
                "annual report",
                "directors' report",
                "directors report",
                "board's report",
                "independent auditor's report",
            )
        ):
            return DocumentType.ANNUAL_REPORT
        if "balance sheet" in normalized and any(
            phrase in normalized
            for phrase in ("profit and loss", "statement of profit", "cash flow statement")
        ):
            return DocumentType.FINANCIAL_STATEMENT
        return DocumentType.UNKNOWN
