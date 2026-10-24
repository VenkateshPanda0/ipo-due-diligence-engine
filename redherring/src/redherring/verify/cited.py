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


def check_cited_number(value: CitedNumber, page_text: PageText) -> Verification:
    reasons: list[str] = []
    if _squash(value.raw) not in _squash(value.span):
        reasons.append(f"raw value {value.raw!r} not in cited span")
    if value.pdf_page not in value.table_pages:
        reasons.append(f"cited page {value.pdf_page} not in table pages {value.table_pages}")
    if not number_on_page(value.raw, page_text(value.pdf_page)):
        reasons.append(f"raw value {value.raw!r} not found on cited page {value.pdf_page}")
    return Verification(ok=not reasons, reasons=reasons)


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
