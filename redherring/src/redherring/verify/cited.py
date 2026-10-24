"""Check that a cited number really is on the page it cites.

The table builder produced the citation, so it cannot grade itself. This module re-reads the page
text straight from the PDF's text layer (a different code path) and checks that the printed number
appears there, that it appears in the cited row text, and that the cited page belongs to the
table. A value failing any check must not be reported.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

import pypdfium2 as pdfium

from redherring.extract.models import CitedNumber

PageText = Callable[[int], str]


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def number_on_page(raw: str, page_text: str) -> bool:
    """Is `raw` (as printed) in `page_text`, ignoring whitespace the extractor may have split?"""
    needle = _squash(raw)
    return bool(needle) and needle in _squash(page_text)


@dataclass(frozen=True)
class Verification:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def check_evidence(
    raw: str,
    span: str,
    pdf_page: int,
    page_text: PageText,
    table_pages: list[int] | None = None,
) -> Verification:
    """Does the evidence hold: `raw` in the span, page within the source, `raw` on the page?"""
    reasons: list[str] = []
    if _squash(raw) not in _squash(span):
        reasons.append(f"raw value {raw!r} not in cited span")
    if table_pages is not None and pdf_page not in table_pages:
        reasons.append(f"cited page {pdf_page} not in table pages {table_pages}")
    if not number_on_page(raw, page_text(pdf_page)):
        reasons.append(f"raw value {raw!r} not found on cited page {pdf_page}")
    return Verification(ok=not reasons, reasons=reasons)


def check_cited_number(value: CitedNumber, page_text: PageText) -> Verification:
    return check_evidence(value.raw, value.span, value.pdf_page, page_text, value.table_pages)


class PdfiumPageText:
    """Page text from the PDF text layer via pypdfium2 (1-based pages), cached per page."""

    def __init__(self, path: Path) -> None:
        self._pdf = pdfium.PdfDocument(str(path))
        self._cache: dict[int, str] = {}

    def __call__(self, pdf_page: int) -> str:
        if pdf_page not in self._cache:
            textpage = self._pdf[pdf_page - 1].get_textpage()
            text: str = textpage.get_text_range()
            textpage.close()
            self._cache[pdf_page] = text
        return self._cache[pdf_page]

    def close(self) -> None:
        self._pdf.close()

    def __enter__(self) -> PdfiumPageText:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
