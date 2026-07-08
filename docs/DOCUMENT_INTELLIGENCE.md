# Document Intelligence

The document-intelligence layer now has real integration points for digital PDFs, tables, OCR fallback, and LLM-backed structured extraction.

## Components

- `PDFParser` uses `pdfplumber` for digital PDFs and preserves 1-based page numbers.
- `PDFParser` calls `OCREngine.extract_page_text()` when a page has poor text quality.
- `OCREngine` renders PDF pages with `pypdfium2` and sends page images to Tesseract via `pytesseract`.
- `TableDetector` uses `pdfplumber.extract_tables()` for real PDF table grids and keeps page numbers on each table.
- `AIExtractor` keeps the deterministic embedded JSON block path for tests, then falls back to local label/table pattern extraction.
- `ConfidenceScorer` now considers extraction method, corroboration, source count, and text quality.

## Runtime Requirements

Python packages are declared in `pyproject.toml`:

- `pdfplumber`
- `pypdfium2`
- `pytesseract`
- `pillow`
For OCR, install the Tesseract binary on the host and ensure it is on `PATH`.

No cloud API key is required for extraction. The extractor is self-contained and deterministic.

## Validation Requirement

Before claiming production readiness, run the extractor against 5-10 real DRHPs or annual reports and compare the extracted fields against a manually verified answer key. At minimum, validate:

- company name, CIN, incorporation date, and registered office,
- revenue, operating profit, PAT, net worth, NTA, monetary assets, assets, liabilities, paid-up capital, reserves, and EBITDA for each fiscal year,
- promoter holding, post-issue holding, and lock-in period,
- issue size, pre-issue net worth, post-issue paid-up capital, market cap, and public offer percentage,
- board/audit committee composition,
- litigation, related-party transactions, and auditor qualifications,
- page numbers and raw snippets for every material value.

The current automated tests verify the plumbing with binary PDFs, pdfplumber tables, and local label/table extraction. They do not replace real document validation.

Use `scripts/validate_documents.py` with a manifest of real PDFs and manually checked expected `CompanyData` JSON files to calculate field-level extraction accuracy.
