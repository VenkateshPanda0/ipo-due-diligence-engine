"""Ingestion security and pipeline behaviour on SYNTHETIC messy documents.

These fixtures test layouts and failure handling. They are not real-world
validation; see docs/BENCHMARK.md for real-document results.
"""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

import pikepdf
import pytest

from app.intelligence.ingest import sanitize_filename, validate_pdf
from app.intelligence.ocr import ocr_available
from app.intelligence.pipeline import PipelineConfig, PipelineResult, run_pipeline
from app.models.exceptions import DocumentRejectedError
from tests.fixtures.pdf_factory import (
    DocSpec,
    PageSpec,
    build_pdf,
    eligibility_table,
    rasterize,
    split_table_drhp,
    standard_drhp,
    text_image_pdf,
)

needs_ocr = pytest.mark.skipif(not ocr_available(), reason="Tesseract binary not installed")
FY24_NTA = "financials.fiscal_years[FY2024].net_tangible_assets"


def run(pdf: bytes, **cfg: Any) -> PipelineResult:
    return run_pipeline(
        pdf,
        filename="t.pdf",
        document_id="0" * 64,
        company_name="Acme",
        config=PipelineConfig(**cfg),
    )


def outcome(r: PipelineResult, path: str) -> Any:
    return next((o for o in r.outcomes if o.field_path == path), None)


def value(r: PipelineResult, path: str) -> Decimal | None:
    o = outcome(r, path)
    return None if o is None or o.selected is None else Decimal(o.selected["value"])


# ---------------------------------------------------------------- ingestion
def _blank_pdf(**save: Any) -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page()
    buf = io.BytesIO()
    pdf.save(buf, **save)
    return buf.getvalue()


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"", "empty"),
        (b"PK\x03\x04 zip", "not_pdf"),
        (b"%PDF-1.4\nnot really", "corrupt"),
    ],
)
def test_rejects_bad_files(content: bytes, reason: str) -> None:
    with pytest.raises(DocumentRejectedError) as exc:
        validate_pdf(content, "x.pdf", max_bytes=10**7, max_pages=10)
    assert exc.value.reason == reason


def test_rejects_encrypted_and_limits() -> None:
    with pytest.raises(DocumentRejectedError) as exc:
        validate_pdf(
            _blank_pdf(encryption=pikepdf.Encryption(user="u", owner="o")),
            "x.pdf",
            max_bytes=10**7,
            max_pages=10,
        )
    assert exc.value.reason == "encrypted"
    with pytest.raises(DocumentRejectedError) as exc:
        validate_pdf(_blank_pdf(), "x.pdf", max_bytes=100, max_pages=10)
    assert exc.value.reason == "too_large"
    with pytest.raises(DocumentRejectedError) as exc:
        validate_pdf(standard_drhp(), "x.pdf", max_bytes=10**7, max_pages=2)
    assert exc.value.reason == "too_many_pages"


def test_repairs_damaged_xref() -> None:
    info = validate_pdf(
        _blank_pdf().replace(b"xref", b"xrfe"), "x.pdf", max_bytes=10**7, max_pages=10
    )
    assert info.repaired and info.warnings


def test_flags_javascript() -> None:
    pdf = pikepdf.new()
    pdf.add_blank_page()
    pdf.Root.OpenAction = pikepdf.Dictionary(
        S=pikepdf.Name.JavaScript, JS=pikepdf.String("app.alert(1)")
    )
    buf = io.BytesIO()
    pdf.save(buf)
    info = validate_pdf(buf.getvalue(), "x.pdf", max_bytes=10**7, max_pages=10)
    assert any("JavaScript" in w for w in info.warnings)


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("../../etc/passwd", "passwd"),
        ("..\\..\\boot.ini", "boot.ini"),
        ("a<script>.pdf", "a_script_.pdf"),
        ("", "document.pdf"),
        (".hidden.pdf", "hidden.pdf"),
        ("x\x00y.pdf", "xy.pdf"),
        ("a" * 300 + ".pdf", "a" * 150),
    ],
)
def test_sanitize_filename(raw: str, clean: str) -> None:
    assert sanitize_filename(raw) == clean


# ---------------------------------------------------------------- native layouts
def test_clean_native_lakhs() -> None:
    r = run(standard_drhp())
    o = outcome(r, FY24_NTA)
    assert o.status.value == "extracted_high_confidence"
    assert o.selected["value"] == "123.4567" and o.selected["original_text"] == "12,345.67"
    assert o.selected["original_unit"] == "INR_LAKH" and o.selected["page_number"] == 2
    assert o.selected["statement_basis"] == "consolidated"
    assert r.doc_type == "drhp"
    assert r.suggestions["listing_route"]["value"] == "mainboard_reg6_1"
    # the "% of NTA" row is never taken as an amount
    assert not any(
        "monetary" in o.field_path and o.selected and o.selected["value"] == "10.00"
        for o in r.outcomes
    )


def test_million_units_and_negative_parentheses() -> None:
    vals = {
        "Net tangible assets": ("1,234.57", "987.65", "765.43"),
        "Operating profit": ("321.00", "(210.05)", "195.03"),
    }
    r = run(standard_drhp(unit_text="(Amount in ₹ million)", values=vals))
    assert value(r, FY24_NTA) == Decimal("123.457")
    assert value(r, "financials.fiscal_years[FY2023].operating_profit") == Decimal("-21.005")


def test_missing_unit_is_not_normalised() -> None:
    r = run(standard_drhp(unit_text=None))
    o = outcome(r, FY24_NTA)
    assert o.status.value == "extracted_needs_verification" and o.selected is None
    assert "unit" in o.reason
    assert "financials" not in r.payload or not r.payload["financials"].get("fiscal_years")


def test_dash_is_missing_not_zero() -> None:
    vals = {"Net tangible assets, as restated": ("12,345.67", "-", "7,654.32")}
    r = run(standard_drhp(values=vals))
    o = outcome(r, "financials.fiscal_years[FY2023].net_tangible_assets")
    assert o.status.value == "not_found" and o.selected is None
    assert "not treated as zero" in o.reason


def test_stub_period_kept_separate() -> None:
    r = run(
        standard_drhp(
            headers=("Six months ended September 30, 2024", "Fiscal 2024", "Fiscal 2023"),
            values={"Net worth, as restated": ("16,000.00", "15,000.00", "12,000.00")},
        )
    )
    assert value(r, "financials.fiscal_years[FY2024].net_worth") == Decimal("150")
    stub = next(
        fy for fy in r.payload["financials"]["fiscal_years"] if fy["year_label"].startswith("P2024")
    )
    assert stub["months"] == 6


def test_conflicting_tables_are_surfaced() -> None:
    conflict = PageSpec(
        lines=["SUMMARY OF RESTATED CONSOLIDATED FINANCIAL INFORMATION"],
        table=eligibility_table(
            values={"Net worth, as restated": ("16,500.00", "12,000.00", "10,000.00")}
        ),
    )
    r = run(standard_drhp(extra_pages=[conflict]))
    o = outcome(r, "financials.fiscal_years[FY2024].net_worth")
    assert o.status.value == "conflicting_candidates"
    assert "165" in o.reason and o.selected["conflicting_values"]
    agree = outcome(r, "financials.fiscal_years[FY2023].net_worth")
    assert agree.status.value == "extracted_high_confidence"  # corroborated by 2 tables


def test_consolidated_preferred_over_standalone() -> None:
    standalone = PageSpec(
        lines=["Restated Standalone financial information"],
        table=eligibility_table(
            basis="Restated Standalone",
            values={"Net worth, as restated": ("9,000.00", "8,000.00", "7,000.00")},
        ),
    )
    r = run(standard_drhp(extra_pages=[standalone]))
    assert value(r, "financials.fiscal_years[FY2024].net_worth") == Decimal("150")
    o = outcome(r, "financials.fiscal_years[FY2024].net_worth")
    assert o.status.value == "extracted_high_confidence"
    assert any(
        c["basis"] == "standalone" for c in o.candidates
    )  # kept as alternative, not a conflict


def test_table_split_across_pages() -> None:
    r = run(split_table_drhp())
    assert value(r, FY24_NTA) == Decimal("123.4567")
    nw = outcome(r, "financials.fiscal_years[FY2024].net_worth")
    assert nw.selected["page_number"] == 3 and nw.selected["original_unit"] == "INR_LAKH"


def test_no_tables_reports_warning_and_fabricates_nothing() -> None:
    r = run(build_pdf(DocSpec([PageSpec(lines=["Annual Report 2024", "Chairman's letter only."])])))
    assert r.tables_found == 0 and "No period-based financial tables were found." in r.warnings
    assert set(r.payload) == {"identification"}


def test_ocr_disabled_marks_scans_unreadable() -> None:
    r = run(text_image_pdf(["DRAFT RED HERRING PROSPECTUS"]), ocr_enabled=False)
    assert r.unreadable_pages == [1]
    assert any("could not be read" in w for w in r.warnings)


def test_environment_recorded_for_reproducibility() -> None:
    r = run(standard_drhp())
    assert r.environment["pipeline_version"] and r.environment["pdfplumber"]
    assert r.config["ocr_dpi"] == 200 and r.metrics["pages"] == 3


# ---------------------------------------------------------------- OCR paths
@needs_ocr
@pytest.mark.slow
@pytest.mark.parametrize(
    "kwargs",
    [
        dict(dpi=200),
        dict(dpi=200, skew_deg=1.5, noise=0.002),
        dict(dpi=200, rotate=90),
        dict(dpi=170, blur=0.6),
    ],
    ids=["scan", "skewed-noisy", "rotated-90", "low-res-blurred"],
)
def test_scanned_variants(kwargs: dict[str, Any]) -> None:
    r = run(rasterize(standard_drhp(), **kwargs))
    o = outcome(r, FY24_NTA)
    assert o is not None and o.selected is not None, r.warnings
    assert Decimal(o.selected["value"]) == Decimal("123.4567")
    # OCR values are never HIGH confidence automatically
    assert o.status.value == "extracted_needs_verification"
    assert o.selected["extraction_method"] == "ocr"
    assert r.metrics["ocr_pages"] == 3


@needs_ocr
@pytest.mark.slow
def test_sideways_native_table_falls_back_to_ocr() -> None:
    pdf = build_pdf(
        DocSpec(
            [
                PageSpec(lines=["DRAFT RED HERRING PROSPECTUS"]),
                PageSpec(rotate_content=True, table=eligibility_table()),
            ]
        )
    )
    r = run(pdf)
    assert r.pages[1]["kind"] == "rotated" and r.pages[1]["method"] == "ocr"
    assert value(r, FY24_NTA) == Decimal("123.4567")


@needs_ocr
@pytest.mark.slow
def test_mixed_native_and_scanned_pages() -> None:
    native = standard_drhp()
    scanned_extra = rasterize(
        build_pdf(DocSpec([PageSpec(lines=["SUMMARY"], table=eligibility_table())])), dpi=200
    )
    merged = pikepdf.new()
    for src in (native, scanned_extra):
        with pikepdf.open(io.BytesIO(src)) as p:
            merged.pages.extend(p.pages)
    buf = io.BytesIO()
    merged.save(buf)
    r = run(buf.getvalue())
    methods = [p["method"] for p in r.pages]
    assert methods.count("native") == 3 and methods.count("ocr") == 1
    o = outcome(r, FY24_NTA)
    assert o.status.value == "extracted_high_confidence"  # native + OCR agree
    assert len({c["method"] for c in o.candidates}) == 2


@needs_ocr
def test_ocr_page_budget() -> None:
    r = run(rasterize(standard_drhp(), dpi=120), max_ocr_pages=1)
    assert r.metrics["ocr_pages"] == 1 and len(r.unreadable_pages) == 2
