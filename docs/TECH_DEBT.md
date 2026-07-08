# Technical Debt Register

## High Impact

- Real PDF text extraction, table extraction, OCR hooks, and deterministic local label/table extraction are now wired behind the parser boundary. Production acceptance still requires validation against 5-10 real DRHPs/annual reports with manually checked expected values.
- Tesseract OCR requires a host-level Tesseract binary in addition to the Python `pytesseract` package.
- The local extractor is intentionally conservative. Unknown labels or incomplete financial tables fail loudly with `ExtractionError` instead of inventing missing fields.
- Regulatory completeness is not legally certified. Keep `REGULATORY_VALIDATION_CONFIRMED=false` until `docs/REGULATORY_VALIDATION.md` is satisfied.
- Human-review storage is in-memory. Production use needs durable append-only audit storage, reviewer identity integration, and role-based authorization.

## Medium Impact

- Persistence is in-memory. Reports and human reviews are lost when the API process restarts.
- API-key authentication is available when `API_KEY` is configured; role-based authorization is not implemented.
- Module-specific coverage thresholds are documented; current tooling enforces an overall threshold.

## Low Impact

- FastAPI/Starlette emits deprecation warnings from the installed test-client stack.
- Some generated coverage artifacts are local-only and should remain ignored.
