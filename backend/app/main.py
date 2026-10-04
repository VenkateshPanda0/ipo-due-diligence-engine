"""FastAPI application assembly."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import Container
from app.api.middleware import register_exception_handlers, request_id_middleware
from app.api.routers import health, reports, reviews, rules, screen, v1
from app.core.config import Settings, get_settings
from app.core.constants import API_VERSION
from app.core.logging import configure_logging
from app.core.security import parse_api_keys


def create_app(settings: Settings | None = None, *, inline_processing: bool = False) -> FastAPI:
    """Create the application. ``inline_processing`` runs document jobs synchronously (tests)."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    parse_api_keys(settings)  # fail fast on malformed API_KEYS
    container = Container.build(settings, inline_processing=inline_processing)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        container.startup()
        yield
        container.shutdown()

    app = FastAPI(
        title="IPO Due Diligence Engine",
        description=(
            "Decision-support screening of Indian main-board IPO eligibility against a versioned, "
            "explicitly scoped ruleset. Not legal advice."
        ),
        version=API_VERSION,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )
    app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )
    app.middleware("http")(request_id_middleware)
    register_exception_handlers(app)
    for router in (health.router, screen.router, reports.router, reviews.router, rules.router):
        app.include_router(router)
    app.include_router(v1.router)
    return app


app = create_app()
