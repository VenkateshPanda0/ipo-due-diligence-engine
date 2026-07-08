"""FastAPI application assembly."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import register_exception_handlers, request_id_middleware
from app.api.routers import health, reports, reviews, rules, screen
from app.core.config import get_settings
from app.core.constants import API_VERSION
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="IPO Due Diligence Engine",
        description="Deterministic SEBI/NSE/BSE IPO eligibility evaluator.",
        version=API_VERSION,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )
    app.middleware("http")(request_id_middleware)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(screen.router)
    app.include_router(reports.router)
    app.include_router(reviews.router)
    app.include_router(rules.router)
    return app


app = create_app()
