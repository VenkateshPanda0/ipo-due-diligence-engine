"""Health endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_settings, get_rule_registry
from app.api.schemas.response_schemas import HealthResponse, ReadinessResponse
from app.core.config import Settings
from app.core.constants import API_VERSION
from app.rules.registry import RuleRegistry

router = APIRouter(tags=["health"])
_STARTED_AT = datetime.now(tz=UTC)


@router.get("/health", response_model=HealthResponse)
def health(registry: RuleRegistry = Depends(get_rule_registry)) -> HealthResponse:
    """Return basic system health."""
    uptime = datetime.now(tz=UTC) - _STARTED_AT
    return HealthResponse(
        status="ok",
        version=API_VERSION,
        ruleset_version=registry.version,
        rules_count=len(registry),
        uptime_seconds=Decimal(str(round(uptime.total_seconds(), 3))),
    )


@router.get("/ready", response_model=ReadinessResponse)
def readiness(
    settings: Settings = Depends(get_app_settings),
    registry: RuleRegistry = Depends(get_rule_registry),
) -> ReadinessResponse:
    """Return production-readiness checks without claiming legal accuracy."""
    checks = {
        "rules_loaded": len(registry) > 0,
        "api_key_configured": settings.api_key is not None,
        "regulatory_validation_confirmed": settings.regulatory_validation_confirmed,
    }
    warnings: list[str] = []
    if not checks["api_key_configured"]:
        warnings.append("API_KEY is not configured; screening endpoints are unauthenticated.")
    if not checks["regulatory_validation_confirmed"]:
        warnings.append(
            "Regulatory validation is not confirmed; do not use results as legal advice."
        )
    production_ready = all(checks.values())
    return ReadinessResponse(
        status="ready" if production_ready else "needs_attention",
        production_ready=production_ready,
        checks=checks,
        warnings=warnings,
    )
