"""
Pipeline orchestration (Stages A–K) and CompanyData assembly.

Output is a *partial* CompanyData payload: only fields with a selected candidate
are populated; everything else is absent (never fabricated). Each populated value
is an ExtractedValue carrying page, original text/unit, period, basis, method,
confidence and field status. Every field decision — including NOT_FOUND and
conflicts — is returned for persistence and the review workspace.
"""

from __future__ import annotations

import logging
import platform
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.intelligence import PIPELINE_VERSION
from app.intelligence.candidates import Candidate, FieldDecision, decide, generate, validate
from app.intelligence.narrative import extract_narrative
from app.intelligence.ocr import deskew_supported, ocr_available, tesseract_version
from app.intelligence.pages import PageData, PageExtractionConfig, extract_pages
from app.intelligence.tables import extract_tables
from app.models.enums import ConfidenceLevel, ExtractionMethod, FieldStatus, StatementBasis
from app.models.extracted_value import ExtractedValue
from app.models.field_paths import FISCAL_YEAR_FIELDS, fiscal_year_path, set_value

logger = logging.getLogger(__name__)
ProgressFn = Callable[[str, int], None]


@dataclass
class PipelineConfig:
    ocr_enabled: bool = True
    max_ocr_pages: int = 60
    ocr_dpi: int = 200
    timeout_s: int = 900

    def as_dict(self) -> dict[str, Any]:
        return {
            "ocr_enabled": self.ocr_enabled,
            "max_ocr_pages": self.max_ocr_pages,
            "ocr_dpi": self.ocr_dpi,
            "timeout_s": self.timeout_s,
        }


@dataclass
class FieldOutcome:
    field_path: str
    status: FieldStatus
    selected: dict[str, Any] | None
    candidates: list[dict[str, Any]]
    reason: str
    score: float | None = None


@dataclass
class PipelineResult:
    pipeline_version: str
    doc_type: str
    pages: list[dict[str, object]]
    tables_found: int
    outcomes: list[FieldOutcome]
    payload: dict[str, Any]
    suggestions: dict[str, dict[str, object]]
    warnings: list[str]
    metrics: dict[str, float | int]
    environment: dict[str, Any]
    config: dict[str, Any]
    unreadable_pages: list[int] = field(default_factory=list)


def environment_info() -> dict[str, Any]:
    from importlib.metadata import PackageNotFoundError, version

    def v(pkg: str) -> str | None:
        try:
            return version(pkg)
        except PackageNotFoundError:
            return None

    return {
        "pipeline_version": PIPELINE_VERSION,
        "python": platform.python_version(),
        "pdfplumber": v("pdfplumber"),
        "pypdfium2": v("pypdfium2"),
        "pikepdf": v("pikepdf"),
        "pytesseract": v("pytesseract"),
        "tesseract": tesseract_version(),
        "ocr_available": ocr_available(),
        "deskew_available": deskew_supported(),
    }


def _confidence(status: FieldStatus, score: float) -> ConfidenceLevel:
    if status == FieldStatus.EXTRACTED_HIGH_CONFIDENCE:
        return ConfidenceLevel.HIGH
    return ConfidenceLevel.MEDIUM if score >= 0.6 else ConfidenceLevel.LOW


def _method(c: Candidate) -> ExtractionMethod:
    return ExtractionMethod.OCR if c.method == "table_ocr" else ExtractionMethod.PDF_TABLE


def _basis(b: str | None) -> StatementBasis:
    return {
        "consolidated": StatementBasis.CONSOLIDATED,
        "standalone": StatementBasis.STANDALONE,
    }.get(b or "", StatementBasis.UNKNOWN)


def _ev_from_candidate(
    d: FieldDecision, filename: str, document_id: str
) -> ExtractedValue[Decimal]:
    c = d.selected
    assert c is not None and c.value is not None
    others = sorted(
        {f"{x.value:.4f}" for x in d.candidates if x.value is not None and x.value != c.value}
    )
    notes = [d.reason] + c.warnings
    if c.original_unit and c.original_unit != "INR_CRORE":
        notes.insert(0, f"Converted {c.original_text} {c.original_unit} → {c.value} INR_CRORE")
    return ExtractedValue[Decimal](
        value=c.value,
        source_document=filename,
        document_id=document_id,
        page_number=c.page,
        extraction_method=_method(c),
        confidence=_confidence(d.status, c.score),
        raw_text=c.context,
        unit="INR_CRORE",
        original_text=c.original_text,
        original_unit=c.original_unit,
        period_label=c.period_label,
        statement_basis=_basis(c.basis),
        field_status=d.status,
        conflicting_values=others if d.status == FieldStatus.CONFLICTING_CANDIDATES else [],
        notes=notes,
    )


def run_pipeline(
    content: bytes,
    *,
    filename: str,
    document_id: str,
    company_name: str,
    config: PipelineConfig,
    progress: ProgressFn | None = None,
) -> PipelineResult:
    """Run the full extraction pipeline on validated PDF bytes."""
    t0 = time.monotonic()
    report = progress or (lambda _stage, _pct: None)
    pages: list[PageData] = extract_pages(
        content,
        PageExtractionConfig(
            config.ocr_enabled, config.max_ocr_pages, config.ocr_dpi, t0 + config.timeout_s
        ),
        progress=lambda stage, pct: report(stage, int(pct * 0.7)),
    )
    t_pages = time.monotonic()
    report("tables", 72)
    tables = extract_tables(pages)
    t_tables = time.monotonic()
    report("candidates", 85)
    candidates = generate(tables)
    by_path: dict[str, list[Candidate]] = {}
    for c in candidates:
        by_path.setdefault(c.field_path, []).append(c)
    decisions = {path: decide(path, cands) for path, cands in by_path.items()}
    validation_notes = validate(decisions)
    narrative = extract_narrative(pages)
    report("assembling", 95)

    payload: dict[str, Any] = {"identification": {"company_name": company_name}}
    outcomes: list[FieldOutcome] = []
    periods_with_values: dict[str, tuple[str | None, int]] = {}
    for path, d in sorted(decisions.items()):
        selected_json: dict[str, Any] | None = None
        if (
            d.selected is not None
            and d.selected.value is not None
            and d.status
            in (
                FieldStatus.EXTRACTED_HIGH_CONFIDENCE,
                FieldStatus.EXTRACTED_NEEDS_VERIFICATION,
                FieldStatus.CONFLICTING_CANDIDATES,
            )
        ):
            ev = _ev_from_candidate(d, filename, document_id)
            selected_json = ev.model_dump(mode="json")
            payload = set_value(payload, path, selected_json, period_end=d.selected.period_end)
            periods_with_values[d.selected.period_label] = (
                d.selected.period_end,
                d.selected.months,
            )
        outcomes.append(
            FieldOutcome(
                path,
                d.status,
                selected_json,
                [c.to_dict() for c in sorted(d.candidates, key=lambda x: -x.score)[:8]],
                d.reason,
                d.selected.score if d.selected else None,
            )
        )
    # Record months / period_end on assembled fiscal years.
    for fy in payload.get("financials", {}).get("fiscal_years", []):
        end, months = periods_with_values.get(fy["year_label"], (None, 12))
        fy["months"] = months
        if end:
            fy["period_end"] = end
    # Explicit NOT_FOUND outcomes for critical fields of detected 12-month periods.
    for label, (_end, months) in periods_with_values.items():
        if months != 12:
            continue
        for f in FISCAL_YEAR_FIELDS:
            path = fiscal_year_path(label, f)
            if path not in decisions:
                outcomes.append(
                    FieldOutcome(path, FieldStatus.NOT_FOUND, None, [], "No candidate found.")
                )
    bases = [
        d.selected.basis for d in decisions.values() if d.selected and d.selected.value is not None
    ]
    if bases:
        cons = bases.count("consolidated")
        stand = bases.count("standalone")
        payload.setdefault("financials", {})["statement_basis"] = (
            "consolidated" if cons >= stand and cons else ("standalone" if stand else "unknown")
        )
    for fact in narrative.facts:
        ev = ExtractedValue[Any](
            value=fact.value,
            source_document=filename,
            document_id=document_id,
            page_number=fact.page,
            extraction_method=ExtractionMethod.NATIVE_TEXT,
            confidence=ConfidenceLevel.MEDIUM,
            raw_text=fact.snippet,
            unit=fact.unit,
            original_text=fact.snippet[:120],
            field_status=FieldStatus.EXTRACTED_NEEDS_VERIFICATION,
            notes=[f"Narrative pattern '{fact.pattern}'; confirm against the source sentence."],
        )
        selected_json = ev.model_dump(mode="json")
        payload = set_value(payload, fact.field_path, selected_json)
        outcomes.append(
            FieldOutcome(
                fact.field_path,
                FieldStatus.EXTRACTED_NEEDS_VERIFICATION,
                selected_json,
                [],
                "Extracted from narrative text; requires verification.",
            )
        )

    unreadable = [p.number for p in pages if not p.readable]
    warnings = sorted({w for p in pages for w in p.warnings if "deskew" not in w})
    if unreadable:
        warnings.insert(0, f"{len(unreadable)} page(s) could not be read: {unreadable[:20]}")
    if not tables:
        warnings.append("No period-based financial tables were found.")
    if narrative.doc_type == "unknown":
        warnings.append(
            "Document type not recognised "
            "(expected DRHP/RHP, annual report or financial statements)."
        )
    warnings.extend(validation_notes)
    t_end = time.monotonic()
    metrics: dict[str, float | int] = {
        "pages": len(pages),
        "native_pages": sum(1 for p in pages if p.method == "native"),
        "ocr_pages": sum(1 for p in pages if p.method == "ocr"),
        "unreadable_pages": len(unreadable),
        "tables": len(tables),
        "candidates": len(candidates),
        "fields_high": sum(
            1 for o in outcomes if o.status == FieldStatus.EXTRACTED_HIGH_CONFIDENCE
        ),
        "fields_needs_verification": sum(
            1 for o in outcomes if o.status == FieldStatus.EXTRACTED_NEEDS_VERIFICATION
        ),
        "fields_conflicting": sum(
            1 for o in outcomes if o.status == FieldStatus.CONFLICTING_CANDIDATES
        ),
        "fields_not_found": sum(1 for o in outcomes if o.status == FieldStatus.NOT_FOUND),
        "seconds_pages": round(t_pages - t0, 3),
        "seconds_tables": round(t_tables - t_pages, 3),
        "seconds_total": round(t_end - t0, 3),
    }
    report("done", 100)
    return PipelineResult(
        pipeline_version=PIPELINE_VERSION,
        doc_type=narrative.doc_type,
        pages=[p.summary() for p in pages],
        tables_found=len(tables),
        outcomes=outcomes,
        payload=payload,
        suggestions=narrative.suggestions,
        warnings=warnings,
        metrics=metrics,
        environment=environment_info(),
        config=config.as_dict(),
        unreadable_pages=unreadable,
    )
