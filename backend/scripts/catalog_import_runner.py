"""scripts/catalog_import_runner.py — Cloud Run Job entrypoint (§9.4, §10.2, Phase 5B).

Usage (Cloud Run Job):
    python -m scripts.catalog_import_runner --job-id <job_id>

Triggered by `routers.catalog.create_import_job` via the Cloud Run Admin
API (`JobsClient.run_job(..., overrides={"args": ["--job-id", job.job_id]})`).
Runs the four-stage pipeline to completion, updating the
`catalog_import_jobs/{job_id}` Firestore document's `status`/`progress`
throughout so `GET /catalog/import/{job_id}` reflects live progress.

Exits non-zero on failure so the Cloud Run Job execution is marked Failed
and shows up in Cloud Logging / any alerting built on job-execution status.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog

from agents.base import AgentContext
from agents.catalog_import import CatalogImportAgent
from config import get_settings
from models.common import ImportStatus
from services.bigquery import BigQueryService
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService
from services.storage import StorageService

logger = structlog.get_logger(__name__)


async def run_import(job_id: str) -> int:
    settings = get_settings()
    firestore = FirestoreService(
        project_id=settings.gcp_project_id, database=settings.firestore_database
    )

    job = await firestore.get_catalog_import_job(job_id)
    if job is None:
        logger.error("catalog_import_job_not_found", job_id=job_id)
        return 1
    if job.status not in (ImportStatus.PENDING,):
        logger.warning("catalog_import_job_not_pending", job_id=job_id, status=job.status.value)
        # Idempotency guard: a retried Cloud Run Job execution for an
        # already-running/finished job is a no-op rather than a double-run.
        return 0

    context = AgentContext(
        settings=settings,
        firestore=firestore,
        embeddings=EmbeddingsService(
            project_id=settings.gcp_project_id,
            location=settings.vertex_ai_location,
            model_name=settings.gemini_embedding_model,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            batch_sleep_seconds=settings.EMBEDDING_BATCH_SLEEP_SECONDS,
        ),
        storage=StorageService(project_id=settings.gcp_project_id, bucket_name=settings.gcs_bucket),
        bigquery=BigQueryService(
            project_id=settings.gcp_project_id,
            dataset=settings.bq_dataset,
            events_table=settings.bq_events_table,
        ),
        store_id=job.store_id,
        claims={"uid": job.initiated_by_uid, "role": "system"},
    )

    agent = CatalogImportAgent(context)
    try:
        await agent.run(job=job)
        logger.info("catalog_import_job_complete", job_id=job_id)
        return 0
    except Exception as exc:
        logger.error("catalog_import_job_failed", job_id=job_id, error=str(exc))
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True, help="catalog_import_jobs document id")
    args = parser.parse_args()

    exit_code = asyncio.run(run_import(args.job_id))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
