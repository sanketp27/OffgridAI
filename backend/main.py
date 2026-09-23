"""main.py — FastAPI application factory.

Entry point: `uvicorn main:app` (see Dockerfile / §10.2 Cloud Run Services).
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agents.base import AgentContext
from agents.orchestrator import Orchestrator
from config import get_settings
from routers import catalog, fit_check, insights, return_intel, search
from services.bigquery import BigQueryService
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService
from services.storage import StorageService

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="OffGrid AI Backend",
        description="Platform-agnostic retail intelligence layer — search, fit-check, "
        "return intelligence, and merchant insights.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def _startup() -> None:
        app.state.firestore = FirestoreService(
            project_id=settings.gcp_project_id, database=settings.firestore_database
        )
        app.state.embeddings = EmbeddingsService(
            project_id=settings.gcp_project_id,
            location=settings.vertex_ai_location,
            model_name=settings.gemini_embedding_model,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            batch_sleep_seconds=settings.EMBEDDING_BATCH_SLEEP_SECONDS,
        )
        app.state.storage = StorageService(
            project_id=settings.gcp_project_id, bucket_name=settings.gcs_bucket
        )
        app.state.bigquery = BigQueryService(
            project_id=settings.gcp_project_id,
            dataset=settings.bq_dataset,
            events_table=settings.bq_events_table,
        )

        def _context_factory(*, store_id: str, claims: dict) -> AgentContext:
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

    # ------------------------------------------------------------------ #
    # Global exception handling
    # ------------------------------------------------------------------ #
    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
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
