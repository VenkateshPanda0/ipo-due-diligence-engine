"""Screening endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.dependencies import get_screening_service
from app.api.schemas.request_schemas import CompanyDataSchema
from app.api.schemas.response_schemas import ScreeningResponse
from app.core.constants import MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_MB, PDF_MEDIA_TYPES
from app.core.security import require_api_key
from app.services.screening_service import ScreeningService

router = APIRouter(prefix="/screen", tags=["screening"], dependencies=[Depends(require_api_key)])


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
    file: UploadFile,
    service: ScreeningService = Depends(get_screening_service),
) -> ScreeningResponse:
    """Screen a company from an uploaded PDF."""
    if file.content_type not in PDF_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF uploads are supported.",
        )
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds the {MAX_UPLOAD_SIZE_MB} MB limit.",
        )
    report = service.screen_pdf(file.filename or "uploaded.pdf", content)
    return ScreeningResponse.from_report(report)
