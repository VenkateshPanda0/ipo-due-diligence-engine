"""
Stage E — OCR fallback (Tesseract via pytesseract), page-level.

Steps per page: render with pdfium at the configured DPI → detect orientation
(Tesseract OSD) and rotate → deskew (projection-profile search, NumPy/Pillow) → OCR with
word boxes and confidences. Word boxes are mapped back to PDF points so OCR words
share the native-text layout model.

OCR availability is detected at runtime; when Tesseract is missing the pipeline
reports the limitation instead of treating the page as empty.
"""

from __future__ import annotations

import io
import logging
import re
import shutil
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image

from app.intelligence.layout import Word

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OCRPage:
    words: list[Word]
    rotation: int
    mean_conf: float | None
    deskew_angle: float | None


@lru_cache(maxsize=1)
def tesseract_version() -> str | None:
    """Return the Tesseract version string, or None if unavailable."""
    if shutil.which("tesseract") is None:
        return None
    try:
        import pytesseract

        return str(pytesseract.get_tesseract_version())
    except Exception:
        return None


def ocr_available() -> bool:
    return tesseract_version() is not None


def deskew_supported() -> bool:
    """Deskew uses numpy/Pillow projection profiles (always available)."""
    return True


def render_page(pdf_bytes: bytes, page_index: int, dpi: int) -> Image.Image:
    """Render one page to a grayscale PIL image."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        page = doc[page_index]
        try:
            bitmap = page.render(scale=dpi / 72)
            image: Image.Image = bitmap.to_pil().convert("L")
        finally:
            page.close()
    finally:
        doc.close()
    return image


def _detect_rotation(image: Image.Image) -> int:
    import pytesseract

    try:
        osd = pytesseract.image_to_osd(image, config="--psm 0 -c min_characters_to_try=20")
    except Exception:
        return 0
    m = re.search(r"Rotate:\s*(\d+)", osd)
    return int(m.group(1)) % 360 if m else 0


def estimate_skew(image: Image.Image, max_angle: float = 5.0, step: float = 0.25) -> float:
    """Estimate text skew (degrees, counter-clockwise positive) by projection profiles.

    The angle that maximises the variance of horizontal ink profiles is the one at
    which text lines are horizontal. Convention-free (no OpenCV angle quirks).
    """
    import numpy as np

    small = image.copy()
    small.thumbnail((900, 900))
    arr = np.asarray(small, dtype=np.uint8)
    ink = (arr < 128).astype(np.uint8) * 255
    if ink.mean() < 0.5:
        return 0.0
    base = Image.fromarray(ink)
    best_angle, best_score = 0.0, -1.0
    angle = -max_angle
    while angle <= max_angle + 1e-9:
        rotated = np.asarray(base.rotate(angle, fillcolor=0), dtype=np.float32)
        score = float(np.var(rotated.sum(axis=1)))
        if score > best_score:
            best_angle, best_score = angle, score
        angle += step
    return -best_angle


def _deskew(image: Image.Image) -> tuple[Image.Image, float | None]:
    try:
        angle = estimate_skew(image)
    except Exception:
        return image, None
    if abs(angle) < 0.3:
        return image, 0.0
    return image.rotate(-angle, expand=True, fillcolor=255), float(angle)


def ocr_page(
    pdf_bytes: bytes, page_index: int, page_width: float, page_height: float, dpi: int
) -> OCRPage:
    """OCR one page and return words in PDF-point coordinates."""
    import pytesseract

    image = render_page(pdf_bytes, page_index, dpi)
    rotation = _detect_rotation(image)
    if rotation:
        image = image.rotate(-rotation, expand=True, fillcolor=255)
    image, deskew_angle = _deskew(image)
    data = pytesseract.image_to_data(image, config="--psm 6", output_type=pytesseract.Output.DICT)
    # After rotation by 90/270 the page's logical width/height swap.
    logical_w, logical_h = (
        (page_height, page_width) if rotation in (90, 270) else (page_width, page_height)
    )
    sx = logical_w / image.width
    sy = logical_h / image.height
    words: list[Word] = []
    confs: list[float] = []
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        x, y, w, h = (data[k][i] for k in ("left", "top", "width", "height"))
        words.append(Word(text, x * sx, (x + w) * sx, y * sy, (y + h) * sy, conf))
        confs.append(conf)
    mean = sum(confs) / len(confs) if confs else None
    return OCRPage(words, rotation, mean, deskew_angle)


def image_bytes_png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
