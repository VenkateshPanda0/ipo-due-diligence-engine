"""Rule Explorer endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_rule_registry
from app.api.schemas.response_schemas import RuleDetailSchema, RuleListResponse
from app.core.security import require_api_key
from app.models.enums import RuleCategory
from app.rules.base_rule import BaseRule
from app.rules.registry import RuleRegistry

router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=RuleListResponse)
def list_rules(
    category: RuleCategory | None = Query(default=None),
    registry: RuleRegistry = Depends(get_rule_registry),
) -> RuleListResponse:
    """List registered rules with optional category filtering."""
    rules = registry.get_all_rules()
    if category is not None:
        rules = [rule for rule in rules if rule.category == category]
    mandatory_count = len(registry.get_mandatory_rules())
    advisory_count = len(registry.get_advisory_rules())
    return RuleListResponse(
        rules=[_rule_detail(rule) for rule in rules],
        total_count=len(rules),
        ruleset_version="1.0.0",
        categories={"mandatory": mandatory_count, "advisory": advisory_count},
    )


@router.get("/{rule_id}", response_model=RuleDetailSchema)
def get_rule_detail(
    rule_id: str,
    registry: RuleRegistry = Depends(get_rule_registry),
) -> RuleDetailSchema:
    """Return detail for a single rule."""
    try:
        rule = registry.get_rule(rule_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return _rule_detail(rule)


def _rule_detail(rule: BaseRule) -> RuleDetailSchema:
    metadata = rule.metadata
    clause = f" {metadata.clause}" if metadata.clause else ""
    return RuleDetailSchema(
        rule_id=rule.rule_id,
        category=rule.category,
        metadata=metadata,
        regulation_reference=f"{metadata.regulation} {metadata.section}{clause}",
        threshold=getattr(rule, "_required_value", metadata.description),
    )
