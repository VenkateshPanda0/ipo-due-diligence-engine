"""Document extraction service."""

from __future__ import annotations

from app.models.company_data import CompanyData
from app.models.exceptions import ExtractionError, UnsupportedDocumentError
from app.parser.ai_extractor import AIExtractor
from app.parser.document_classifier import DocumentClassifier, DocumentType
from app.parser.ocr_engine import OCREngine
from app.parser.pdf_parser import PDFParser
from app.parser.table_detector import TableDetector


class ExtractionService:
    """Coordinate parser components to produce CompanyData from documents."""

    def __init__(
        self,
        pdf_parser: PDFParser | None = None,
        classifier: DocumentClassifier | None = None,
        extractor: AIExtractor | None = None,
        ocr_engine: OCREngine | None = None,
        table_detector: TableDetector | None = None,
    ) -> None:
        self._ocr_engine = ocr_engine or OCREngine()
        self._pdf_parser = pdf_parser or PDFParser(ocr_engine=self._ocr_engine)
        self._classifier = classifier or DocumentClassifier()
        self._extractor = extractor or AIExtractor()
        self._table_detector = table_detector or TableDetector()

    def extract_company_data(self, filename: str, content: bytes) -> CompanyData:
        """Extract canonical CompanyData from uploaded document bytes."""
        pages = self._pdf_parser.extract_text(content)
        text = "\n\n".join(f"=== Page {page.page_number} ===\n{page.text}" for page in pages)
        quality = self._pdf_parser.assess_quality(text)
        if not quality.is_usable:
            text = self._ocr_engine.extract_text(content)
        table_text = self._extract_table_context(content)
        if table_text:
            text = f"{text}\n\n=== Extracted Tables ===\n{table_text}"
        document_type = self._classifier.classify(text)
        if document_type == DocumentType.UNKNOWN:
            raise UnsupportedDocumentError(filename)
        try:
            return self._extractor.extract_company_data(text)
        except ExtractionError:
            raise

    def _extract_table_context(self, content: bytes) -> str:
        if content.startswith(b"%PDF"):
            tables = self._table_detector.extract_tables_from_pdf(content)
        else:
            pages = self._pdf_parser.extract_text(content)
            tables = [
                table
                for page in pages
                for table in self._table_detector.extract_tables_from_text(
                    page.text, page_number=page.page_number
                )
            ]
        lines: list[str] = []
        for table_index, table in enumerate(tables, start=1):
            lines.append(
                f"Table {table_index} page {table.page_number} "
                f"method {table.extraction_method}"
            )
            lines.extend(" | ".join(row) for row in table.rows)
        return "\n".join(lines)
