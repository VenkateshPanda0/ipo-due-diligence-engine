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
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import pdfplumber

from app.intelligence.layout import Line, Word, build_lines
from app.intelligence.ocr import ocr_available, ocr_page
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


def looks_tabular(lines: list[Line]) -> bool:
    """True if any line has at least two cells that parse as reporting periods."""
    return any(sum(1 for c in line.cells if parse_period(c.text)) >= 2 for line in lines)


@dataclass
class PageExtractionConfig:
    ocr_enabled: bool = True
    max_ocr_pages: int = 60
    ocr_dpi: int = 200
    deadline: float | None = None  # monotonic timestamp


def extract_pages(
    content: bytes,
    config: PageExtractionConfig,
    progress: Callable[[str, int], None] | None = None,
) -> list[PageData]:
    """Run classification + native extraction + OCR fallback for all pages."""
    pages: list[PageData] = []
    can_ocr = config.ocr_enabled and ocr_available()
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        total = len(pdf.pages)
        for idx, page in enumerate(pdf.pages):
            if config.deadline is not None and time.monotonic() > config.deadline:
                pages.append(
                    PageData(
                        idx + 1,
                        float(page.width),
                        float(page.height),
                        "unprocessed",
                        "none",
                        readable=False,
                        warnings=["processing time budget exhausted"],
                    )
                )
                continue
            try:
                raw_words = page.extract_words(
                    keep_blank_chars=False, use_text_flow=False, extra_attrs=["upright"]
                )
            except Exception as exc:  # malformed content stream on one page
                logger.warning(
                    "page_text_error", extra={"page": idx + 1, "error": type(exc).__name__}
                )
                raw_words = []
            text = " ".join(w["text"] for w in raw_words)
            upright = (
                (sum(1 for w in raw_words if w.get("upright", True)) / len(raw_words))
                if raw_words
                else 1.0
            )
            area = float(page.width * page.height) or 1.0
            img_area = 0.0
            for im in page.images:
                img_area += max(0.0, float(im["x1"]) - float(im["x0"])) * max(
                    0.0, float(im["bottom"]) - float(im["top"])
                )
            image_cov = min(1.0, img_area / area)
            garbled = _garbled_ratio(text)
            kind = _classify(len(text), image_cov, upright, garbled)
            data = PageData(
                idx + 1,
                float(page.width),
                float(page.height),
                kind,
                "native",
                char_count=len(text),
                image_coverage=image_cov,
                upright_ratio=upright,
                garbled_ratio=garbled,
            )
            if kind == "native":
                data.words = [
                    Word(
                        w["text"],
                        float(w["x0"]),
                        float(w["x1"]),
                        float(w["top"]),
                        float(w["bottom"]),
                    )
                    for w in raw_words
                    if w.get("upright", True)
                ]
            elif kind == "blank":
                data.method = "none"
            else:
                ocr_used = sum(1 for p in pages if p.method == "ocr")
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
                        res = ocr_page(content, idx, data.width, data.height, config.ocr_dpi)
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
                    data.native_tables = page.extract_tables() or []
                except Exception:
                    data.warnings.append("vector table extraction failed on this page")
            pages.append(data)
            page.close()
            if progress and (idx % 10 == 0 or idx == total - 1):
                progress("extracting", int((idx + 1) / total * 100))
    return pages
