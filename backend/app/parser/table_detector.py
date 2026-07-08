"""Table extraction interfaces for document intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

from app.models.exceptions import ExtractionError


@dataclass(frozen=True)
class ExtractedTable:
    """A table extracted from a document page."""

    page_number: int
    rows: list[list[str]]
    extraction_method: str


class TableDetector:
    """Extract tables from real PDFs with a text fallback for tests."""

    def extract_tables_from_pdf(self, content: bytes) -> list[ExtractedTable]:
        """Extract tables from PDF bytes using pdfplumber table extraction."""
        try:
            pdfplumber = self._import_module("pdfplumber")
            tables: list[ExtractedTable] = []
            with pdfplumber.open(BytesIO(content)) as pdf:
                for index, page in enumerate(pdf.pages, start=1):
                    for raw_table in page.extract_tables() or []:
                        rows = self._normalise_rows(raw_table)
                        if rows:
                            tables.append(
                                ExtractedTable(
                                    page_number=index,
                                    rows=rows,
                                    extraction_method="pdfplumber",
                                )
                            )
            return tables
        except Exception as exc:
            raise ExtractionError("pdf_tables", f"Unable to extract PDF tables: {exc}") from exc

    def extract_tables_from_text(self, text: str, page_number: int = 1) -> list[ExtractedTable]:
        """Extract pipe-delimited tables from text."""
        rows = [
            [cell.strip() for cell in line.strip("|").split("|")]
            for line in text.splitlines()
            if line.count("|") >= 2
        ]
        if not rows:
            return []
        return [ExtractedTable(page_number=page_number, rows=rows, extraction_method="text")]

    @staticmethod
    def _normalise_rows(raw_table: list[list[Any]]) -> list[list[str]]:
        rows: list[list[str]] = []
        for raw_row in raw_table:
            row = [
                " ".join(str(cell or "").replace("\n", " ").split())
                for cell in raw_row
            ]
            if any(cell for cell in row):
                rows.append(row)
        return rows

    @staticmethod
    def _import_module(name: str) -> Any:
        try:
            module = __import__(name)
        except ImportError as exc:  # pragma: no cover - exercised when deps absent
            raise ExtractionError("pdf_tables", f"Missing table dependency: {name}") from exc
        return module
