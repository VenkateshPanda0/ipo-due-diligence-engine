"""
API middleware and exception handlers.

All errors use one envelope: ``{"error": {"code", "message", "request_id", "details"?}}``.
Only whitelisted, primitive details are returned; exception internals, stack traces
and file paths are never sent to clients (baseline defect D13).
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.models.exceptions import DomainError

logger = logging.getLogger("app.api")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_STATUS_BY_CODE = {
    "UNSUPPORTED_DOCUMENT": status.HTTP_501_NOT_IMPLEMENTED,  # kept for API v0 compatibility
    "REPORT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "INVALID_STATE": status.HTTP_409_CONFLICT,
    "CONFLICT": status.HTTP_409_CONFLICT,
    "DOCUMENT_REJECTED": 422,
}


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", ""))


def error_response(
    request: Request, status_code: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message, "request_id": _request_id(request)}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=jsonable_encoder({"error": body}))


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach a validated X-Request-ID and log one structured line per request."""
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if _REQUEST_ID_RE.match(incoming) else str(uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
    return response


def register_exception_handlers(app: FastAPI) -> None:
    """Register the standard error envelope handlers."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        code = exc.error_code
        http_status = getattr(exc, "http_status", None) or _STATUS_BY_CODE.get(code, 422)
        return error_response(
            request,
            http_status,
            code,
            exc.message,
            exc.public_details(),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "loc": [str(p) for p in err.get("loc", ())],
                "msg": str(err.get("msg", "")),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ]
        return error_response(
            request, 422, "VALIDATION_ERROR", "Request validation failed.", details
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        details = [
            {
                "loc": [str(p) for p in err.get("loc", ())],
                "msg": str(err.get("msg", "")),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ]
        return error_response(request, 422, "VALIDATION_ERROR", "Data validation failed.", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            413: "PAYLOAD_TOO_LARGE",
            415: "UNSUPPORTED_MEDIA_TYPE",
            429: "RATE_LIMITED",
        }.get(exc.status_code, "HTTP_ERROR")
        response = error_response(request, exc.status_code, code, str(exc.detail))
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", extra={"request_id": _request_id(request)})
        return error_response(
            request,
            500,
            "INTERNAL_ERROR",
            "An internal error occurred. Quote the request ID when reporting it.",
        )
