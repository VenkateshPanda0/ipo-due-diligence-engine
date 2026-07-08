"""OCR fallback for scanned PDF documents."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from app.models.exceptions import ExtractionError


class OCREngine:
    """Extract text from scanned PDF pages using pypdfium2 + Tesseract.

    The Python packages are loaded lazily so tests can inject this class without
    importing native OCR dependencies at module import time. A working Tesseract
    binary must still be installed on the host for production OCR.
    """

    def extract_text(self, content: bytes) -> str:
        """OCR all pages in a PDF and return page-separated text."""
        page_texts: list[str] = []
        page_count = self._page_count(content)
        for page_number in range(1, page_count + 1):
            text = self.extract_page_text(content, page_number)
            if text:
                page_texts.append(text)
        return "\f".join(page_texts)

    def extract_page_text(self, content: bytes, page_number: int) -> str:
        """OCR a single 1-based page from PDF bytes."""
        try:
            pypdfium2 = self._import_module("pypdfium2")
            pytesseract = self._import_module("pytesseract")
            pdf = pypdfium2.PdfDocument(BytesIO(content))
            page = pdf[page_number - 1]
            image = page.render(scale=2).to_pil()
            return str(pytesseract.image_to_string(image)).strip()
        except Exception as exc:  # pragma: no cover - depends on native OCR runtime
            raise ExtractionError("ocr", f"OCR failed on page {page_number}: {exc}") from exc

    def _page_count(self, content: bytes) -> int:
        try:
            pypdfium2 = self._import_module("pypdfium2")
            pdf = pypdfium2.PdfDocument(BytesIO(content))
            return len(pdf)
        except Exception as exc:  # pragma: no cover - depends on native OCR runtime
            raise ExtractionError("ocr", f"Unable to render PDF for OCR: {exc}") from exc

    @staticmethod
    def _import_module(name: str) -> Any:
        try:
            module = __import__(name)
        except ImportError as exc:  # pragma: no cover - exercised when deps absent
            raise ExtractionError("ocr", f"Missing OCR dependency: {name}") from exc
        return module
