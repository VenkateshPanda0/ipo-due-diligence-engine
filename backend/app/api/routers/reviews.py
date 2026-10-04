"""Human review endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_human_review_service
from app.api.schemas.request_schemas import HumanReviewDecisionRequest
from app.api.schemas.response_schemas import HumanReviewResponse
from app.core.security import Principal, require_api_key, require_reviewer_role
from app.services.review_service import HumanReviewService

router = APIRouter(
    prefix="/reviews",
    tags=["human-review"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/reports/{report_id}", response_model=HumanReviewResponse)
def open_review(
    report_id: UUID,
    service: HumanReviewService = Depends(get_human_review_service),
    principal: Principal = Depends(require_api_key),
) -> HumanReviewResponse:
    """Open or return the human review for a machine-generated report."""
    return HumanReviewResponse.from_domain(service.open_review(report_id, actor=principal.user_id))


@router.get("/{review_id}", response_model=HumanReviewResponse)
def get_review(
    review_id: UUID,
    service: HumanReviewService = Depends(get_human_review_service),
) -> HumanReviewResponse:
    """Return a human review record."""
    return HumanReviewResponse.from_domain(service.get_review(review_id))


@router.post("/{review_id}/decision", response_model=HumanReviewResponse)
def complete_review(
    review_id: UUID,
    request: HumanReviewDecisionRequest,
    service: HumanReviewService = Depends(get_human_review_service),
    principal: Principal = Depends(require_reviewer_role),
) -> HumanReviewResponse:
    """Record the human final decision for a review."""
    return HumanReviewResponse.from_domain(
        service.complete_review(
            review_id,
            reviewer_name=request.reviewer_name,
            final_decision=request.final_decision,
            rationale=request.rationale,
            conditions=request.conditions,
            actor=principal.user_id,
        )
    )
