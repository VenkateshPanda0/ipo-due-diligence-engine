"""
backend/app/models/exceptions.py

Domain exception hierarchy for the IPO Due Diligence Engine.

Services raise domain exceptions; the handlers in ``app.api.middleware`` translate
them into the API error envelope. Rules never raise for missing data — they return
an INCONCLUSIVE result instead.

This module MUST NOT import from:
  - app.rules, app.intelligence, app.api, app.engine
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
