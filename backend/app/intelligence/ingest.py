"""
Stage A — secure ingestion.

* File type is established from the byte signature, never the filename or MIME type.
* Size and page limits are enforced before any heavy parsing.
* Encrypted PDFs are rejected with a clear reason (no password guessing).
* Damaged PDFs are opened with pikepdf's repairing parser; if that fails the file
  is rejected. Embedded JavaScript / attachments are detected and reported, never
  executed (no component in this pipeline executes PDF content).
* Stored filenames are server-generated; the original name is sanitised for
  display only.
"""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field

import pikepdf

from app.models.exceptions import DocumentRejectedError

PDF_MAGIC = b"%PDF-"
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._ ()-]+")


@dataclass(frozen=True)
class IngestResult:
    """Validated document facts."""

    sha256: str
    size_bytes: int
    page_count: int
    pdf_version: str
    display_name: str
    warnings: list[str] = field(default_factory=list)
    repaired: bool = False


def sanitize_filename(name: str | None) -> str:
    """Return a display-safe filename (no path components, control chars or traversal)."""
    raw = (name or "document.pdf").replace("\\", "/").split("/")[-1]
    raw = unicodedata.normalize("NFKC", raw)
    raw = "".join(ch for ch in raw if ch.isprintable())
    cleaned = _SAFE_NAME_RE.sub("_", raw).strip(" .")
    cleaned = cleaned.lstrip(".") or "document.pdf"
    return cleaned[:150]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_pdf(
    content: bytes, filename: str | None, *, max_bytes: int, max_pages: int
) -> IngestResult:
    """Validate an uploaded PDF. Raises DocumentRejectedError with a reason code."""
    if not content:
        raise DocumentRejectedError("empty", "The uploaded file is empty.")
    if len(content) > max_bytes:
        raise DocumentRejectedError(
            "too_large", f"File exceeds the {max_bytes // (1024 * 1024)} MB limit."
        )
    head = content[:1024]
    if PDF_MAGIC not in head:
        raise DocumentRejectedError(
            "not_pdf", "The file is not a PDF (PDF signature not found in the file header)."
        )
    warnings: list[str] = []
    if not head.startswith(PDF_MAGIC):
        warnings.append("PDF signature is preceded by extra bytes")
    try:
        pdf = pikepdf.open(io.BytesIO(content))
    except pikepdf.PasswordError as exc:
        raise DocumentRejectedError(
            "encrypted", "The PDF is password-protected. Upload an unencrypted copy."
        ) from exc
    except pikepdf.PdfError as exc:
        raise DocumentRejectedError(
            "corrupt", "The PDF is damaged and could not be repaired."
        ) from exc
    with pdf:
        parser_warnings = list(pdf.get_warnings())
        repaired = bool(parser_warnings)
        if repaired:
            warnings.append(
                f"PDF structure was damaged and repaired ({len(parser_warnings)} parser warnings)"
            )
        if pdf.is_encrypted:
            # Owner-password-only PDFs open without a user password; content is readable.
            warnings.append("PDF has owner-password restrictions (content readable)")
        page_count = len(pdf.pages)
        if page_count == 0:
            raise DocumentRejectedError("no_pages", "The PDF has no pages.")
        if page_count > max_pages:
            raise DocumentRejectedError(
                "too_many_pages", f"The PDF has {page_count} pages; the limit is {max_pages}."
            )
        root = pdf.Root
        names = root.get("/Names")
        if root.get("/OpenAction") is not None or (
            names is not None and names.get("/JavaScript") is not None
        ):
            warnings.append("PDF contains JavaScript/open actions (ignored, never executed)")
        if names is not None and names.get("/EmbeddedFiles") is not None:
            warnings.append("PDF contains embedded files (ignored)")
        version = str(pdf.pdf_version)
    return IngestResult(
        sha256=sha256_bytes(content),
        size_bytes=len(content),
        page_count=page_count,
        pdf_version=version,
        display_name=sanitize_filename(filename),
        warnings=warnings,
        repaired=repaired,
    )
