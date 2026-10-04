"""System-wide constants for the IPO Due Diligence Engine."""

from __future__ import annotations

API_VERSION = "2.0.0"
DEFAULT_RULESET_VERSION = "2.0.0"
MAX_UPLOAD_SIZE_MB = 10
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
SUPPORTED_DOCUMENT_TYPES = ("annual_report", "drhp", "financial_statement")
DEFAULT_REPORT_FORMAT = "json"
PDF_MEDIA_TYPES = ("application/pdf", "application/octet-stream")
