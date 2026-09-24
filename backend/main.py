"""main.py — FastAPI application factory.

Entry point: `uvicorn main:app` (see Dockerfile / §10.2 Cloud Run Services).

Client-freshness notes (audited when this file was integrated into the
common/core scaffold):
  * Startup wiring moved from `@app.on_event("startup")` to the `lifespan`
    context-manager pattern — `on_event` has been deprecated by FastAPI
    for several releases in favor of `lifespan`.
  * Every `services/*Service` now takes a single `Settings` instance
    instead of individual positional args, matching the constructor
    signature change made across `services/` during this integration.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agents.base import AgentContext
from agents.orchestrator import Orchestrator
from config import get_settings
from core.exceptions import DependencyError, NotFoundError, OffGridError, capture_exception
from core.logging import configure_logging, get_logger
from routers import catalog, fit_check, insights, return_intel, search
from services.bigquery import BigQueryService
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService
from services.storage import StorageService

settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)

# Maps an OffGridError family to the HTTP status code its API response
# should carry. Anything not listed here (a bug, not an expected failure
# mode) falls through to the catch-all 500 handler below.
_STATUS_CODE_BY_ERROR: dict[type[OffGridError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    DependencyError: status.HTTP_502_BAD_GATEWAY,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.firestore = FirestoreService(settings)
    app.state.embeddings = EmbeddingsService(settings)
    app.state.storage = StorageService(settings)
    app.state.bigquery = BigQueryService(settings)

    def _context_factory(*, store_id: str, claims: dict[str, Any]) -> AgentContext:
        return AgentContext(
            settings=settings,
            firestore=app.state.firestore,
            embeddings=app.state.embeddings,
            storage=app.state.storage,
            bigquery=app.state.bigquery,
            store_id=store_id,
            claims=claims,
        )

    app.state.orchestrator = Orchestrator(_context_factory)
    logger.info("startup_complete", env=settings.env, project=settings.gcp_project_id)

    yield

    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="OffGrid AI Backend",
        description="Platform-agnostic retail intelligence layer — search, fit-check, "
        "return intelligence, and merchant insights.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------ #
    # Structured exception handling
    # ------------------------------------------------------------------ #
    @app.exception_handler(OffGridError)
    async def _offgrid_error_handler(request: Request, exc: OffGridError) -> JSONResponse:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        for error_type, code in _STATUS_CODE_BY_ERROR.items():
            if isinstance(exc, error_type):
                status_code = code
                break
        logger.warning(
            "request_failed", path=request.url.path, error=exc.code, message=exc.message,
            context=exc.context,
        )
        return JSONResponse(status_code=status_code, content=exc.to_dict())

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        capture_exception(logger, exc, event="unhandled_exception", path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "message": "Internal server error"},
        )

    # ------------------------------------------------------------------ #
    # Health check (no auth — §7.1)
    # ------------------------------------------------------------------ #
    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ------------------------------------------------------------------ #
    # Routers (§10.1)
    # ------------------------------------------------------------------ #
    app.include_router(search.router)
    app.include_router(fit_check.router)
    app.include_router(return_intel.router)
    app.include_router(insights.router)
    app.include_router(catalog.router)

    return app


app = create_app()
