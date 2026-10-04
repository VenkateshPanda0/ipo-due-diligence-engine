"""API middleware and exception handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.models.exceptions import (
    DomainError,
    ReportNotFoundError,
    UnsupportedDocumentError,
)


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach an X-Request-ID header to each response."""
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def register_exception_handlers(app: FastAPI) -> None:
    """Register standard domain and validation exception handlers."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        if isinstance(exc, UnsupportedDocumentError):
            status_code = status.HTTP_501_NOT_IMPLEMENTED
        elif isinstance(exc, ReportNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(
                {
                    "error": {
                        "code": exc.error_code,
                        "message": exc.message,
                        "details": getattr(exc, "__dict__", {}),
                    }
                }
            ),
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
        )
