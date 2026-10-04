"""Report retrieval endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.api.dependencies import get_report_service
from app.core.security import require_api_key
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_api_key)])

_MEDIA_TYPES = {
    "json": "application/json",
    "html": "text/html",
    "text": "text/plain",
}


@router.get("/{report_id}")
def get_report(
    report_id: UUID,
    format: str = Query(default="json", pattern="^(json|html|text)$"),
    service: ReportService = Depends(get_report_service),
) -> Response:
    """Retrieve a previously generated report."""
    rendered = service.get_report(report_id, format)
    headers = (
        {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"}
        if format == "html"
        else {}
    )
    return Response(content=rendered, media_type=_MEDIA_TYPES[format], headers=headers)
