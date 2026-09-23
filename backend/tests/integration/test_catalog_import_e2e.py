"""tests/integration/test_catalog_import_e2e.py — full Catalog Import Agent pipeline.

Excluded from the default `pytest` run — see `tests/integration/test_search_flow.py`
for the emulator/dev-project setup this depends on.
"""

from __future__ import annotations

import uuid

import pytest

from agents.base import AgentContext
from agents.catalog_import import CatalogImportAgent
from config import get_settings
from models.catalog_import_job import CatalogImportJob
from models.common import ImportStatus
from services.bigquery import BigQueryService
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService
from services.storage import StorageService


@pytest.mark.integration
async def test_url_import_against_a_small_test_storefront() -> None:
    """Smoke test: crawl a small, fixture storefront (2-3 pages), run all
    four pipeline stages, and assert:
      * `catalog_import_jobs/{job_id}.status == "done"`
      * `progress.pages_crawled > 0`
      * at least one new `SKU` document written with a non-empty `embedding`
      * the GCS report at `result.gcs_report_path` exists and is valid JSON

    Left unimplemented (`pytest.skip`) in the scaffold -- point
    `input_source` at a controlled test fixture (not a live third-party
    site) once the emulator/dev project + a disposable GCS bucket are wired
    into CI, so this test isn't flaky against a real external storefront.
    """
    pytest.skip("Wire up the Firestore emulator / dev project + a fixture storefront before enabling.")

    settings = get_settings()
    context = AgentContext(
        settings=settings,
        firestore=FirestoreService(settings.gcp_project_id, settings.firestore_database),
        embeddings=EmbeddingsService(settings.gcp_project_id, settings.vertex_ai_location),
        storage=StorageService(settings.gcp_project_id, settings.gcs_bucket),
        bigquery=BigQueryService(settings.gcp_project_id, settings.bq_dataset),
        store_id="store_001",
    )
    job = CatalogImportJob(
        job_id=str(uuid.uuid4()),
        store_id="store_001",
        initiated_by_uid="test-admin",
        input_type="url",
        input_source="https://example-test-storefront.local/",
        status=ImportStatus.PENDING,
    )
    await context.firestore.create_catalog_import_job(job)

    completed = await CatalogImportAgent(context).run(job=job)

    assert completed.status == ImportStatus.DONE
    assert completed.result is not None
    assert completed.result.skus_added > 0


@pytest.mark.integration
async def test_dry_run_writes_no_catalog_documents() -> None:
    """`dry_run=True` must produce full progress/preview data without ever
    calling `FirestoreService.upsert_sku`.
    """
    pytest.skip("Wire up the Firestore emulator / dev project before enabling this test.")
