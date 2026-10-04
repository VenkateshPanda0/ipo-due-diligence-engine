"""Screening endpoints (API v0, kept for backward compatibility)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.api.dependencies import Container, get_container, get_screening_service
from app.api.routers.v1 import _read_limited
from app.api.schemas.request_schemas import CompanyDataSchema
from app.api.schemas.response_schemas import ScreeningResponse
from app.core.security import require_api_key
from app.services.screening_service import ScreeningService

router = APIRouter(
    prefix="/screen", tags=["screening (v0)"], dependencies=[Depends(require_api_key)]
)


@router.post("/json", response_model=ScreeningResponse)
def screen_json(
    request: CompanyDataSchema,
    service: ScreeningService = Depends(get_screening_service),
) -> ScreeningResponse:
    """Screen a company from canonical CompanyData JSON."""
    report = service.screen_json(request.to_domain())
    return ScreeningResponse.from_report(report)


@router.post("/pdf", response_model=ScreeningResponse)
async def screen_pdf(
    file: UploadFile = File(...),
    c: Container = Depends(get_container),
) -> ScreeningResponse:
    """Screen a company from one uploaded PDF (synchronous; prefer /api/v1 cases).

    The file type is established from its bytes, not the declared content type.
    """
    content = await _read_limited(file, c.settings.max_upload_size_bytes)
    report = await run_in_threadpool(
        c.screening.screen_pdf, file.filename or "uploaded.pdf", content
    )
    return ScreeningResponse.from_report(report)
