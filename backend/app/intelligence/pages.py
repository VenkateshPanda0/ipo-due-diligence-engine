"""
Stages B, C and E — page classification, native text extraction and per-page
OCR fallback.

Each page is classified independently (mixed documents are common):

  native      — enough upright, well-formed native text
  scanned     — little/no native text and significant image coverage → OCR
  rotated     — native text mostly non-upright (sideways tables) → OCR with OSD
  garbled     — native text present but broken font mapping (high ratio of
                replacement / private-use / non-printable characters) → OCR
  blank       — no text and no images

OCR runs only for pages that need it, within a per-document page budget and an
overall time budget. A page that needed OCR but could not get it is reported as
UNREADABLE, never silently treated as an empty valid page.
"""

from __future__ import annotations

import io
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import pdfplumber

from app.intelligence.layout import Line, Word, build_lines
from app.intelligence.ocr import ocr_available, ocr_image, render_pdfium_page
from app.intelligence.periods import parse_period

logger = logging.getLogger(__name__)

MIN_NATIVE_CHARS = 40


@dataclass
class PageData:
    number: int  # 1-based
    width: float
    height: float
    kind: str
    method: str  # "native" | "ocr" | "none"
    words: list[Word] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    text: str = ""
    char_count: int = 0
    image_coverage: float = 0.0
    upright_ratio: float = 1.0
    garbled_ratio: float = 0.0
    ocr_mean_conf: float | None = None
    rotation: int = 0
    warnings: list[str] = field(default_factory=list)
    readable: bool = True
    native_tables: list[list[list[str | None]]] = field(default_factory=list)

    def summary(self) -> dict[str, object]:
        return {
            "page": self.number,
            "kind": self.kind,
            "method": self.method,
            "chars": self.char_count,
            "image_coverage": round(self.image_coverage, 3),
            "upright_ratio": round(self.upright_ratio, 3),
            "garbled_ratio": round(self.garbled_ratio, 3),
            "ocr_mean_conf": None if self.ocr_mean_conf is None else round(self.ocr_mean_conf, 1),
            "rotation": self.rotation,
            "readable": self.readable,
            "warnings": self.warnings,
        }


def _garbled_ratio(text: str) -> float:
    if not text:
        return 0.0
    bad = sum(
        1
        for ch in text
        if ch == "�"
        or 0xE000 <= ord(ch) <= 0xF8FF
        or (not ch.isprintable() and ch not in "\n\t ")
        or (0x00 < ord(ch) < 0x20 and ch not in "\n\t")
    )
    cid = text.count("(cid:")
    return min(1.0, (bad + cid * 5) / max(len(text), 1))


def _classify(char_count: int, image_cov: float, upright: float, garbled: float) -> str:
    if char_count < MIN_NATIVE_CHARS:
        if image_cov > 0.15:
            return "scanned"
        return "blank" if char_count == 0 else "native"  # sparse but genuine native text
    if garbled > 0.15:
        return "garbled"
    if upright < 0.5:
        return "rotated"
    return "native"


_DIGITS_RE = re.compile(r"\d\d")


def looks_tabular(lines: list[Line]) -> bool:
    """True if any line has at least two cells that parse as reporting periods.

    Cells without two consecutive digits cannot contain a year, so they are not parsed.
    """
    return any(
        sum(1 for c in line.cells if _DIGITS_RE.search(c.text) and parse_period(c.text)) >= 2
        for line in lines
    )


@dataclass
class PageExtractionConfig:
    ocr_enabled: bool = True
    max_ocr_pages: int = 60
    ocr_dpi: int = 200
    deadline: float | None = None  # monotonic timestamp


def _pdfium_words(page: object, height: float) -> tuple[list[Word], int, float]:
    """Native words from pdfium character boxes. Returns (upright words, char count, upright ratio).

    Characters are grouped into words on whitespace and on horizontal gaps wider than
    a third of the character height. Non-upright characters (|angle| > ~10°) are counted
    for rotation detection but not emitted as words.
    """
    import ctypes

    import pypdfium2.raw as pdfium_c

    textpage = page.get_textpage()  # type: ignore[attr-defined]
    try:
        tp = textpage.raw  # raw handle: avoids per-call wrapper conversion in the hot loop
        n = pdfium_c.FPDFText_CountChars(tp)
        is_generated = pdfium_c.FPDFText_IsGenerated
        get_unicode = pdfium_c.FPDFText_GetUnicode
        get_angle = pdfium_c.FPDFText_GetCharAngle
        get_box = pdfium_c.FPDFText_GetLooseCharBox
        rect = pdfium_c.FS_RECTF()
        rect_ref = ctypes.byref(rect)
        words: list[Word] = []
        chars: list[str] = []
        # bounds of the word being built, and the previous character's box
        x0 = x1 = top = bottom = 0.0
        prev_x1 = prev_top = prev_bottom = 0.0
        upright = 0
        counted = 0

        def flush() -> None:
            if chars:
                words.append(Word("".join(chars), x0, x1, top, bottom))
                chars.clear()

        for k in range(n):
            if is_generated(tp, k):
                flush()
                continue
            code = get_unicode(tp, k)
            ch = chr(code) if code else ""
            if not ch or ch.isspace():
                flush()
                continue
            counted += 1
            angle = get_angle(tp, k)
            if not (angle < 0.17 or angle > 6.11):  # radians, ~10 degrees from upright
                flush()
                continue
            upright += 1
            # Loose boxes use font ascent/descent, so punctuation shares the line's height.
            get_box(tp, k, rect_ref)
            left, right = rect.left, rect.right
            c_top, c_bottom = height - rect.top, height - rect.bottom
            if chars:
                gap = left - prev_x1
                char_h = max(prev_bottom - prev_top, 1.0)
                if gap > char_h * 0.33 or abs(c_top - prev_top) > char_h * 0.6 or gap < -char_h:
                    flush()
            if chars:
                x0, x1 = min(x0, left), max(x1, right)
                top, bottom = min(top, c_top), max(bottom, c_bottom)
            else:
                x0, x1, top, bottom = left, right, c_top, c_bottom
            chars.append(ch)
            prev_x1, prev_top, prev_bottom = right, c_top, c_bottom
        flush()
        return words, counted, (upright / counted) if counted else 1.0
    finally:
        textpage.close()


def _image_coverage(page: object, width: float, height: float) -> float:
    import pypdfium2.raw as pdfium_c

    area = 0.0
    try:
        for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE], max_depth=2):  # type: ignore[attr-defined]
            left, bottom, right, top = obj.get_bounds()
            area += max(0.0, right - left) * max(0.0, top - bottom)
    except Exception:
        return 0.0
    return min(1.0, area / max(width * height, 1.0))


def extract_pages(
    content: bytes,
    config: PageExtractionConfig,
    progress: Callable[[str, int], None] | None = None,
) -> list[PageData]:
    """Run classification + native extraction + OCR fallback for all pages.

    Native text and geometry come from pdfium (fast, C); pdfplumber is opened lazily
    only for vector-table extraction on pages that already look tabular.
    """
    import pypdfium2 as pdfium

    pages: list[PageData] = []
    ocr_used = 0
    can_ocr = config.ocr_enabled and ocr_available()
    doc = pdfium.PdfDocument(content)
    plumber: pdfplumber.pdf.PDF | None = None
    try:
        total = len(doc)
        for idx in range(total):
            page = doc[idx]
            try:
                width, height = float(page.get_width()), float(page.get_height())
                if config.deadline is not None and time.monotonic() > config.deadline:
                    pages.append(
                        PageData(
                            idx + 1,
                            width,
                            height,
                            "unprocessed",
                            "none",
                            readable=False,
                            warnings=["processing time budget exhausted"],
                        )
                    )
                    continue
                try:
                    words, char_count, upright = _pdfium_words(page, height)
                except Exception as exc:  # malformed content on one page
                    logger.warning(
                        "page_text_error", extra={"page": idx + 1, "error": type(exc).__name__}
                    )
                    words, char_count, upright = [], 0, 1.0
                text = " ".join(w.text for w in words)
                image_cov = _image_coverage(page, width, height)
            finally:
                page.close()
            garbled = _garbled_ratio(text)
            kind = _classify(char_count, image_cov, upright, garbled)
            data = PageData(
                idx + 1,
                width,
                height,
                kind,
                "native",
                char_count=char_count,
                image_coverage=image_cov,
                upright_ratio=upright,
                garbled_ratio=garbled,
            )
            if kind == "native":
                data.words = words
            elif kind == "blank":
                data.method = "none"
            else:
                if not can_ocr:
                    data.method = "none"
                    data.readable = False
                    data.warnings.append(
                        f"page is {kind}; OCR is "
                        f"{'disabled' if not config.ocr_enabled else 'unavailable'}"
                    )
                elif ocr_used >= config.max_ocr_pages:
                    data.method = "none"
                    data.readable = False
                    data.warnings.append("OCR page budget exhausted")
                else:
                    try:
                        ocr_used += 1
                        page = doc[idx]  # render from the open document (no re-parse)
                        try:
                            image = render_pdfium_page(page, config.ocr_dpi)
                        finally:
                            page.close()
                        res = ocr_image(image, data.width, data.height)
                        data.words, data.rotation, data.ocr_mean_conf = (
                            res.words,
                            res.rotation,
                            res.mean_conf,
                        )
                        data.method = "ocr"
                        if res.deskew_angle:
                            data.warnings.append(f"deskewed by {res.deskew_angle:.1f}°")
                        if not res.words:
                            data.readable = False
                            data.warnings.append("OCR returned no text")
                        elif (res.mean_conf or 0) < 50:
                            data.warnings.append("low OCR confidence")
                    except Exception as exc:
                        data.method = "none"
                        data.readable = False
                        data.warnings.append(f"OCR failed ({type(exc).__name__})")
            data.lines = build_lines(data.words)
            data.text = "\n".join(line.text for line in data.lines)
            if data.method == "native" and looks_tabular(data.lines):
                # Vector/text-alignment tables only where a period header exists (cost control).
                try:
                    if plumber is None:
                        plumber = pdfplumber.open(io.BytesIO(content))
                    pl_page = plumber.pages[idx]
                    data.native_tables = pl_page.extract_tables() or []
                    pl_page.close()
                except Exception:
                    data.warnings.append("vector table extraction failed on this page")
            pages.append(data)
            if progress and (idx % 10 == 0 or idx == total - 1):
                progress("extracting", int((idx + 1) / total * 100))
    finally:
        if plumber is not None:
            plumber.close()
        doc.close()
    return pages
