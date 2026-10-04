"""
API v1 — case-based screening workflow.

    /api/v1/system/{health,ready,capabilities}
    /api/v1/dashboard
    /api/v1/cases [GET, POST]; /cases/{id} [GET, PATCH]
    /api/v1/cases/{id}/data [GET, PUT]; /data/versions; /fields [PATCH]; /history
    /api/v1/cases/{id}/documents [GET, POST]
    /api/v1/documents/{id} [GET]; /retry [POST]; /content [GET, DELETE];
        /extraction [GET]; /pages/{n}/image [GET]
    /api/v1/review-items [GET]; /review-items/{id}/resolve [POST]
    /api/v1/cases/{id}/screenings [GET, POST]
    /api/v1/reports [GET]; /reports/{id} [GET]; /reports/{id}/export?format= [GET]
    /api/v1/reports/{id}/sign-off [GET, POST]
    /api/v1/rulesets; /rules; /rules/{id}

Legacy endpoints (/screen/*, /reports/{id}, /reviews/*, /rules, /health) remain.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.dependencies import Container, get_container
from app.api.schemas.response_schemas import ScreeningResponse
from app.core.constants import API_VERSION
from app.core.security import Principal, Role, get_principal, require_role
from app.intelligence import PIPELINE_VERSION
from app.intelligence.ocr import ocr_available, render_page, tesseract_version
from app.models.enums import ListingRoute
from app.models.exceptions import NotFoundError, ReportNotFoundError
from app.models.human_review import HumanFinalDecision
from app.regulatory.registry import available_ruleset_versions, load_ruleset_summary, load_sources

router = APIRouter(prefix="/api/v1", tags=["v1"])
analyst = require_role(Role.ANALYST)
reviewer = require_role(Role.REVIEWER)
admin = require_role(Role.ADMIN)
_STARTED = datetime.now(tz=UTC)
_UPLOAD_CHUNK = 1024 * 1024


# ----------------------------------------------------------------- schemas
class CaseCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=300)
    listing_route: ListingRoute = ListingRoute.MAINBOARD_REG6_1
    notes: str | None = Field(default=None, max_length=5000)


class CaseUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=300)
    listing_route: ListingRoute | None = None
    notes: str | None = Field(default=None, max_length=5000)
    archived: bool | None = None


class CaseDataReplace(BaseModel):
    payload: dict[str, Any]
    reason: str | None = Field(default=None, max_length=1000)


class FieldUpdate(BaseModel):
    field_path: str = Field(max_length=200)
    value: Any = None
    note: str | None = Field(default=None, max_length=1000)
    period_end: str | None = Field(default=None, max_length=10)


class FieldsUpdate(BaseModel):
    updates: list[FieldUpdate] = Field(min_length=1, max_length=200)


class ResolveRequest(BaseModel):
    action: str = Field(pattern="^(confirm|correct|reject|request_more_evidence)$")
    value: Any = None
    reason: str | None = Field(default=None, max_length=2000)


class SignOffRequest(BaseModel):
    reviewer_name: str = Field(min_length=1, max_length=200)
    final_decision: HumanFinalDecision
    rationale: str = Field(min_length=1, max_length=5000)
    conditions: list[str] = Field(default_factory=list, max_length=50)


# ----------------------------------------------------------------- system
@router.get("/system/health")
def health(c: Container = Depends(get_container)) -> dict[str, Any]:
    """Liveness plus basic dependency status (no authentication)."""
    return {
        "status": "ok",
        "version": API_VERSION,
        "uptime_seconds": round((datetime.now(tz=UTC) - _STARTED).total_seconds(), 1),
        "database": c.db.ping(),
        "ruleset_version": c.registry.version,
    }


@router.get("/system/ready")
def ready(c: Container = Depends(get_container)) -> Response:
    """Readiness: database reachable and rules loaded."""
    ok = c.db.ping() and len(c.registry) > 0
    import json

    body = {"ready": ok, "database": c.db.ping(), "rules_loaded": len(c.registry)}
    return Response(json.dumps(body), status_code=200 if ok else 503, media_type="application/json")


@router.get("/system/capabilities")
def capabilities(
    c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> dict[str, Any]:
    s = c.settings
    rs = c.registry.ruleset
    return {
        "api_version": API_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "ruleset": {
            "version": rs.version,
            "status": rs.status,
            "effective_from": rs.effective_from,
            "supported_routes": rs.supported_routes,
            "unsupported_routes": rs.unsupported_routes,
            "legal_review_confirmed": rs.legal_review.confirmed,
        },
        "regulatory_validation_confirmed": s.regulatory_validation_confirmed,
        "supported_document_types": [
            "application/pdf (DRHP, RHP, prospectus, annual report, financial statements)"
        ],
        "ocr": {
            "enabled": s.ocr_enabled,
            "available": ocr_available(),
            "tesseract_version": tesseract_version(),
            "max_ocr_pages": s.max_ocr_pages,
            "dpi": s.ocr_dpi,
        },
        "limits": {
            "max_upload_size_mb": s.max_upload_size_mb,
            "max_pdf_pages": s.max_pdf_pages,
            "processing_timeout_s": s.processing_timeout_s,
            "upload_rate_per_minute": s.rate_limit_per_minute,
        },
        "auth": {
            "enabled": s.auth_enabled,
            "mode": "api_keys" if s.auth_enabled else "local_single_user",
        },
        "retention": {"retain_documents": s.retain_documents, "retention_days": s.retention_days},
        "database": {"backend": c.db.url.split(":", 1)[0], "reachable": c.db.ping()},
        "external_services": [],
    }


@router.get("/me")
def me(p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return {"user_id": p.user_id, "role": p.role.value, "authenticated": p.authenticated}


@router.get("/dashboard")
def dashboard_view(
    c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> dict[str, Any]:
    from app.services.cases import dashboard

    return {**dashboard(c.db), "ruleset_version": c.registry.version}


# ----------------------------------------------------------------- cases
@router.get("/cases")
def list_cases(
    status_filter: str | None = Query(default=None, alias="status", max_length=40),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    c: Container = Depends(get_container),
    _p: Principal = Depends(get_principal),
) -> dict[str, Any]:
    return c.cases.list_cases(status=status_filter, q=q, limit=limit, offset=offset)


@router.post("/cases", status_code=status.HTTP_201_CREATED)
def create_case(
    body: CaseCreate, c: Container = Depends(get_container), p: Principal = Depends(analyst)
) -> dict[str, Any]:
    return c.cases.create(
        company_name=body.company_name.strip(),
        listing_route=body.listing_route,
        actor=p.user_id,
        notes=body.notes,
    )


@router.get("/cases/{case_id}")
def get_case(
    case_id: UUID, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> dict[str, Any]:
    return c.cases.get(str(case_id))


@router.patch("/cases/{case_id}")
def update_case(
    case_id: UUID,
    body: CaseUpdate,
    c: Container = Depends(get_container),
    p: Principal = Depends(analyst),
) -> dict[str, Any]:
    return c.cases.update(
        str(case_id),
        actor=p.user_id,
        company_name=body.company_name,
        listing_route=body.listing_route,
        notes=body.notes,
        archived=body.archived,
    )


@router.get("/cases/{case_id}/data")
def case_data(
    case_id: UUID,
    version: int | None = Query(default=None, ge=1),
    c: Container = Depends(get_container),
    _p: Principal = Depends(get_principal),
) -> dict[str, Any]:
    return c.cases.data(str(case_id), version)


@router.get("/cases/{case_id}/data/versions")
def case_versions(
    case_id: UUID, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> list[dict[str, Any]]:
    return c.cases.versions(str(case_id))


@router.put("/cases/{case_id}/data")
def replace_case_data(
    case_id: UUID,
    body: CaseDataReplace,
    c: Container = Depends(get_container),
    p: Principal = Depends(analyst),
) -> dict[str, Any]:
    return c.cases.replace_data(str(case_id), body.payload, actor=p.user_id, reason=body.reason)


@router.patch("/cases/{case_id}/fields")
def set_fields(
    case_id: UUID,
    body: FieldsUpdate,
    c: Container = Depends(get_container),
    p: Principal = Depends(analyst),
) -> dict[str, Any]:
    try:
        return c.cases.set_fields(
            str(case_id), [u.model_dump() for u in body.updates], actor=p.user_id
        )
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.get("/cases/{case_id}/history")
def case_history(
    case_id: UUID, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> list[dict[str, Any]]:
    return c.cases.history(str(case_id))


# ----------------------------------------------------------------- documents
async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    """Read an upload in chunks, aborting as soon as the size limit is exceeded."""
    buf = io.BytesIO()
    while True:
        chunk = await upload.read(_UPLOAD_CHUNK)
        if not chunk:
            break
        buf.write(chunk)
        if buf.tell() > limit:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Upload exceeds the {limit // (1024 * 1024)} MB limit.",
            )
    return buf.getvalue()


@router.get("/cases/{case_id}/documents")
def case_documents(
    case_id: UUID, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> list[dict[str, Any]]:
    c.cases.get(str(case_id))
    return c.documents.list_documents(case_id=str(case_id))


@router.post("/cases/{case_id}/documents", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    case_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    c: Container = Depends(get_container),
    p: Principal = Depends(analyst),
) -> dict[str, Any]:
    """Upload a PDF. Validation is synchronous; extraction runs in the background."""
    declared = request.headers.get("content-length")
    if (
        declared
        and declared.isdigit()
        and int(declared) > c.settings.max_upload_size_bytes + 1024 * 64
    ):
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload exceeds the {c.settings.max_upload_size_mb} MB limit.",
        )
    if not c.documents.rate_limiter.allow(p.user_id):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many uploads; try again shortly.",
            headers={"Retry-After": "60"},
        )
    content = await _read_limited(file, c.settings.max_upload_size_bytes)
    return await run_in_threadpool(
        c.documents.upload, str(case_id), file.filename, content, actor=p.user_id
    )


@router.get("/documents")
def list_documents(
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    c: Container = Depends(get_container),
    _p: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    return c.documents.list_documents(status=status_filter)


@router.get("/documents/{document_id}")
def get_document(
    document_id: UUID, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> dict[str, Any]:
    return c.documents.get(str(document_id))


@router.post("/documents/{document_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_document(
    document_id: UUID, c: Container = Depends(get_container), p: Principal = Depends(analyst)
) -> dict[str, Any]:
    return await run_in_threadpool(c.documents.retry, str(document_id), actor=p.user_id)


@router.get("/documents/{document_id}/extraction")
def document_extraction(
    document_id: UUID, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> dict[str, Any]:
    return c.documents.extraction(str(document_id))


@router.get("/documents/{document_id}/content")
def document_content(
    document_id: UUID, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> Response:
    doc = c.documents.get(str(document_id))
    return Response(
        c.documents.content(str(document_id)),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{doc["filename"]}"',
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, max-age=300",
        },
    )


@router.delete("/documents/{document_id}/content")
def delete_document_content(
    document_id: UUID, c: Container = Depends(get_container), p: Principal = Depends(analyst)
) -> dict[str, Any]:
    return c.documents.delete_content(str(document_id), actor=p.user_id)


@router.get("/documents/{document_id}/pages/{page}/image")
async def page_image(
    document_id: UUID,
    page: int,
    dpi: int = Query(default=110, ge=50, le=150),
    c: Container = Depends(get_container),
    _p: Principal = Depends(get_principal),
) -> Response:
    """Render one page as PNG for the evidence viewer."""
    doc = c.documents.get(str(document_id))
    if not 1 <= page <= int(doc["page_count"] or 0):
        raise NotFoundError("page", page)
    content = c.documents.content(str(document_id))

    def render() -> bytes:
        img = render_page(content, page - 1, dpi)
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()

    png = await run_in_threadpool(render)
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


# ----------------------------------------------------------------- review workspace
@router.get("/review-items")
def review_items(
    case_id: UUID | None = None,
    status_filter: str | None = Query(default="open", alias="status", max_length=40),
    c: Container = Depends(get_container),
    _p: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    return c.cases.review_items(str(case_id) if case_id else None, status_filter or None)


@router.post("/review-items/{item_id}/resolve")
def resolve_item(
    item_id: UUID,
    body: ResolveRequest,
    c: Container = Depends(get_container),
    p: Principal = Depends(reviewer),
) -> dict[str, Any]:
    try:
        item = c.cases.resolve_item(
            str(item_id), action=body.action, actor=p.user_id, reason=body.reason, value=body.value
        )
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    c.documents.mark_reviewed_documents(item["case_id"])
    return item


# ----------------------------------------------------------------- screening & reports
@router.post(
    "/cases/{case_id}/screenings",
    status_code=status.HTTP_201_CREATED,
    response_model=ScreeningResponse,
)
async def screen_case(
    case_id: UUID, c: Container = Depends(get_container), p: Principal = Depends(analyst)
) -> ScreeningResponse:
    report = await run_in_threadpool(c.case_screening.screen, str(case_id), actor=p.user_id)
    return ScreeningResponse.from_report(report)


@router.get("/cases/{case_id}/screenings")
def case_screenings(
    case_id: UUID, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> list[dict[str, Any]]:
    c.cases.get(str(case_id))
    return c.case_screening.list_reports(str(case_id))


@router.get("/reports")
def list_reports(
    limit: int = Query(default=50, ge=1, le=200),
    c: Container = Depends(get_container),
    _p: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    return c.case_screening.list_reports(None, limit)


@router.get("/reports/{report_id}", response_model=ScreeningResponse)
def get_report(
    report_id: UUID, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> ScreeningResponse:
    report = c.reports.get(report_id)
    if report is None:
        raise ReportNotFoundError(report_id)
    return ScreeningResponse.from_report(report)


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: UUID,
    format: str = Query(default="html", pattern="^(json|text|html)$"),
    c: Container = Depends(get_container),
    _p: Principal = Depends(get_principal),
) -> Response:
    rendered = c.report_service.get_report(report_id, format)
    media = {
        "json": "application/json",
        "text": "text/plain; charset=utf-8",
        "html": "text/html; charset=utf-8",
    }[format]
    ext = {"json": "json", "text": "txt", "html": "html"}[format]
    headers = {"Content-Disposition": f'attachment; filename="screening-{report_id}.{ext}"'}
    if format == "html":
        headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return Response(rendered, media_type=media, headers=headers)


@router.get("/reports/{report_id}/sign-off")
def get_sign_off(
    report_id: UUID, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> dict[str, Any]:
    review = c.reviews.get_by_report_id(report_id)
    if review is None:
        return {"report_id": str(report_id), "review": None, "history": []}
    return {
        "report_id": str(report_id),
        "review": review.model_dump(mode="json"),
        "history": c.reviews.history(review.review_id),
    }


@router.post("/reports/{report_id}/sign-off")
def sign_off(
    report_id: UUID,
    body: SignOffRequest,
    c: Container = Depends(get_container),
    p: Principal = Depends(reviewer),
) -> dict[str, Any]:
    review = c.human_review.open_review(report_id, actor=p.user_id)
    done = c.human_review.complete_review(
        review.review_id,
        reviewer_name=body.reviewer_name,
        final_decision=body.final_decision,
        rationale=body.rationale,
        conditions=body.conditions,
        actor=p.user_id,
    )
    return {
        "report_id": str(report_id),
        "review": done.model_dump(mode="json"),
        "history": c.reviews.history(done.review_id),
    }


# ----------------------------------------------------------------- regulatory metadata
@router.get("/rulesets")
def rulesets(_p: Principal = Depends(get_principal)) -> list[dict[str, Any]]:
    out = []
    for version in available_ruleset_versions():
        raw = load_ruleset_summary(version)
        out.append(
            {
                k: raw.get(k)
                for k in (
                    "version",
                    "status",
                    "effective_from",
                    "effective_to",
                    "activated_on",
                    "description",
                    "supported_routes",
                    "unsupported_routes",
                    "legal_review",
                    "change_summary",
                )
            }
            | {"rule_count": len(r) if isinstance(r := raw.get("rules"), list) else 0}
        )
    return out


@router.get("/rules")
def rules(
    c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> dict[str, Any]:
    sources = load_sources()
    return {
        "ruleset_version": c.registry.version,
        "rules": [
            {
                **r.spec.model_dump(mode="json"),
                "required_value": r.required_value,
                "sources": [sources[s].model_dump(mode="json") for s in r.spec.source_ids],
            }
            for r in c.registry.get_all_rules()
        ],
    }


@router.get("/rules/{rule_id}")
def rule(
    rule_id: str, c: Container = Depends(get_container), _p: Principal = Depends(get_principal)
) -> dict[str, Any]:
    try:
        r = c.registry.get_rule(rule_id)
    except KeyError as exc:
        raise NotFoundError("rule", rule_id) from exc
    sources = load_sources()
    return {
        **r.spec.model_dump(mode="json"),
        "required_value": r.required_value,
        "sources": [sources[s].model_dump(mode="json") for s in r.spec.source_ids],
    }
