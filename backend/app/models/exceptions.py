"""
backend/app/models/exceptions.py

Domain exception hierarchy for the IPO Due Diligence Engine.

All exceptions carry structured context that can be translated directly
into API error responses by the FastAPI exception handlers in main.py.

Services raise domain exceptions. API handlers translate them to HTTP
responses. Rule implementations raise InsufficientDataError when required
data is absent or unusable.

This module MUST NOT import from:
  - app.rules, app.parser, app.api, app.engine

Error codes match the API error envelope documented in ARCHITECTURE.md §13.3.
"""


class DomainError(Exception):
    """Base class for all domain exceptions in the IPO Due Diligence Engine.

    Every domain error carries an error_code string that maps to the API
    error envelope and a human-readable message.

    Example:
        >>> err = DomainError("Something went wrong")
        >>> err.error_code
        'DOMAIN_ERROR'
    """

    error_code: str = "DOMAIN_ERROR"

    #: Attribute names that are safe to expose to API clients.
    public_fields: tuple[str, ...] = ()

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def public_details(self) -> dict[str, object]:
        """Whitelisted, primitive details safe to return to API clients."""
        out: dict[str, object] = {}
        for name in self.public_fields:
            value = getattr(self, name, None)
            if isinstance(value, (str, int, float, bool)) or value is None:
                out[name] = value
            elif isinstance(value, (list, tuple)):
                out[name] = [str(v) for v in value]
            else:
                out[name] = str(value)
        return out


class InsufficientDataError(DomainError):
    """Raised when CompanyData lacks required fields for a rule evaluation.

    The Rules Engine raises this when a mandatory field is absent from
    CompanyData or when a field's value cannot be used (e.g., None where
    a numeric value is required). The Decision Engine catches this at the
    rule level and records an INCONCLUSIVE verdict rather than crashing.

    Args:
        rule_id: The identifier of the rule that encountered missing data.
        missing_fields: List of field paths that were absent or invalid.

    Example:
        >>> err = InsufficientDataError("NTA_3CR", ["financials.fiscal_years"])
        >>> err.error_code
        'INSUFFICIENT_DATA'
        >>> err.rule_id
        'NTA_3CR'
    """

    error_code: str = "INSUFFICIENT_DATA"
    public_fields = ("rule_id", "fields")

    def __init__(self, rule_id: str, missing_fields: list[str]) -> None:
        self.rule_id = rule_id
        self.fields = missing_fields
        suggestion = "Upload complete annual reports or provide data via /screen/json"
        super().__init__(f"Rule '{rule_id}' requires: {missing_fields}. {suggestion}")


class RuleEvaluationError(DomainError):
    """Raised when a rule encounters an unexpected error during evaluation.

    This signals a programming error (e.g., unexpected data type, division
    by zero not caught by the rule). The Rules Engine logs this and records
    an INCONCLUSIVE verdict rather than propagating the exception.

    Example:
        >>> err = RuleEvaluationError("NET_WORTH_1CR", "division by zero")
        >>> err.error_code
        'RULE_EVALUATION_ERROR'
    """

    error_code: str = "RULE_EVALUATION_ERROR"

    def __init__(self, rule_id: str, detail: str) -> None:
        self.rule_id = rule_id
        super().__init__(f"Rule '{rule_id}' evaluation failed: {detail}")


class ExtractionError(DomainError):
    """Raised when a mandatory field cannot be extracted from a document.

    The Document Intelligence layer raises this when extraction fails for
    a critical field. The Extraction Service converts this to an
    InsufficientDataError before it reaches the Rules Engine.

    Example:
        >>> err = ExtractionError("net_worth", "no table found on page 47")
        >>> err.error_code
        'EXTRACTION_FAILED'
    """

    error_code: str = "EXTRACTION_FAILED"
    public_fields = ("field_name",)

    def __init__(self, field_name: str, reason: str) -> None:
        self.field_name = field_name
        super().__init__(f"Failed to extract '{field_name}': {reason}")


class UnsupportedDocumentError(DomainError):
    """Raised when an uploaded document cannot be classified or processed.

    The Document Classifier raises this when the document type cannot be
    determined (not an Annual Report, DRHP, or Financial Statement).

    Example:
        >>> err = UnsupportedDocumentError("image_scan.pdf")
        >>> err.error_code
        'UNSUPPORTED_DOCUMENT'
    """

    error_code: str = "UNSUPPORTED_DOCUMENT"

    def __init__(self, filename: str) -> None:
        self.filename = filename
        super().__init__(
            f"Document '{filename}' is not a supported type "
            "(expected: Annual Report, DRHP, or Financial Statement)."
        )


class ReportNotFoundError(DomainError):
    """Raised when a report ID does not exist in the store.

    Example:
        >>> import uuid
        >>> report_id = uuid.uuid4()
        >>> err = ReportNotFoundError(report_id)
        >>> err.error_code
        'REPORT_NOT_FOUND'
    """

    error_code: str = "REPORT_NOT_FOUND"
    public_fields = ("report_id",)

    def __init__(self, report_id: object) -> None:
        self.report_id = report_id
        super().__init__(f"Report '{report_id}' not found.")


class RulesetNotFoundError(DomainError):
    """Raised when a requested ruleset version is not available.

    Example:
        >>> err = RulesetNotFoundError("2.0.0")
        >>> err.error_code
        'RULESET_NOT_FOUND'
    """

    error_code: str = "RULESET_NOT_FOUND"

    def __init__(self, version: str) -> None:
        self.version = version
        super().__init__(
            f"Ruleset version '{version}' is not available. "
            "Use GET /rules to see available versions."
        )


class NotFoundError(DomainError):
    """A requested entity does not exist."""

    error_code: str = "NOT_FOUND"
    public_fields = ("entity", "entity_id")

    def __init__(self, entity: str, entity_id: object) -> None:
        self.entity = entity
        self.entity_id = str(entity_id)
        super().__init__(f"{entity} '{entity_id}' not found.")


class InvalidStateError(DomainError):
    """An operation is not allowed in the entity's current state."""

    error_code: str = "INVALID_STATE"
    public_fields = ("entity", "state")

    def __init__(self, entity: str, state: str, message: str) -> None:
        self.entity = entity
        self.state = state
        super().__init__(message)


class DocumentRejectedError(DomainError):
    """An uploaded file failed validation and was not stored."""

    error_code: str = "DOCUMENT_REJECTED"
    public_fields = ("reason",)

    _HTTP_STATUS = {"not_pdf": 415, "too_large": 413}

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        self.http_status = self._HTTP_STATUS.get(reason, 422)
        super().__init__(message)
