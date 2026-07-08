"""PDF text extraction orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

from app.models.exceptions import ExtractionError
from app.parser.ocr_engine import OCREngine


@dataclass(frozen=True)
class PageText:
    """Text extracted from a single document page."""

    page_number: int
    text: str


@dataclass(frozen=True)
class TextQuality:
    """Simple text quality assessment."""

    is_usable: bool
    character_count: int
    word_count: int


class PDFParser:
    """Extract per-page text from uploaded PDF bytes.

    Digital PDFs are read with pdfplumber. Pages with poor text quality are
    sent through OCR, preserving the original 1-based page number for evidence
    citations. Plain UTF-8 fallback remains for tests and local demo payloads
    that are not actual PDF files.
    """

    def __init__(self, ocr_engine: OCREngine | None = None) -> None:
        self._ocr_engine = ocr_engine or OCREngine()

    def extract_text(self, content: bytes) -> list[PageText]:
        """Extract text from PDF bytes, preserving page numbers."""
        if content.startswith(b"%PDF"):
            return self._extract_pdf_text(content)
        return self._extract_text_fallback(content)

    def _extract_pdf_text(self, content: bytes) -> list[PageText]:
        try:
            pdfplumber = self._import_module("pdfplumber")
            pages: list[PageText] = []
            with pdfplumber.open(BytesIO(content)) as pdf:
                for index, page in enumerate(pdf.pages, start=1):
                    text = str(page.extract_text(x_tolerance=1, y_tolerance=3) or "").strip()
                    if not self.assess_quality(text).is_usable:
                        text = self._ocr_engine.extract_page_text(content, index)
                    if text.strip():
                        pages.append(PageText(page_number=index, text=text.strip()))
            return pages
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError("pdf_text", f"Unable to extract PDF text: {exc}") from exc

    def _extract_text_fallback(self, content: bytes) -> list[PageText]:
        """Extract page-separated UTF-8 text for deterministic tests/demos."""
        text = content.decode("utf-8", errors="ignore")
        pages = text.split("\f") if "\f" in text else [text]
        return [
            PageText(page_number=index + 1, text=page.strip())
            for index, page in enumerate(pages)
            if page.strip()
        ]

    def assess_quality(self, text: str) -> TextQuality:
        """Return a deterministic text quality assessment."""
        words = text.split()
        return TextQuality(
            is_usable=len(text.strip()) >= 20 and len(words) >= 3,
            character_count=len(text),
            word_count=len(words),
        )

    @staticmethod
    def _import_module(name: str) -> Any:
        try:
            module = __import__(name)
        except ImportError as exc:  # pragma: no cover - exercised when deps absent
            raise ExtractionError("pdf_text", f"Missing PDF dependency: {name}") from exc
        return module
