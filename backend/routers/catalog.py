"""routers/catalog.py — Catalog read + import-job endpoints (§7.2, §9.4, Phase 5B).

    GET  /catalog/{sku_id}          single SKU lookup
    POST /catalog/import            create a CatalogImportJob and kick off the Cloud Run Job
    GET  /catalog/import/{job_id}   poll job status/progress/result

Note: the actual 4-stage pipeline (`agents.catalog_import.CatalogImportAgent`)
runs inside a Cloud Run Job execution (`scripts/catalog_import_runner.py`),
NOT inline in this request handler -- imports can run for minutes against a
300-page crawl, well past an HTTP request budget. This router's job is only
to validate input, write the `pending` job document, and trigger the job
execution; the runner script does everything else asynchronously.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from config import Settings, get_settings
from dependencies import get_db, require_role, require_store_match
from models.catalog_import_job import CatalogImportJob
from models.common import ImportStatus
from services.firestore import FirestoreService

router = APIRouter(tags=["catalog"])

VALID_INPUT_TYPES = ("url", "pdf", "image", "excel", "csv")


class SKUResponse(BaseModel):
    sku_id: str
    name: str
    description: str
    category: str
    price: float
    currency: str
    stock: int
    return_rate: float
    image_url: str
    attributes: dict[str, str]


class CreateImportJobRequest(BaseModel):
    store_id: str
    input_type: str
    input_source: str  # URL, or a GCS object path for an already-uploaded file
    crawl_depth: int | None = None
    dry_run: bool = False

    @field_validator("input_type")
    @classmethod
    def _valid_input_type(cls, v: str) -> str:
        if v not in VALID_INPUT_TYPES:
            raise ValueError(f"input_type must be one of {VALID_INPUT_TYPES}")
        return v


class ImportJobResponse(BaseModel):
    job_id: str
    store_id: str
    status: str
    input_type: str
    progress: dict
    result: dict | None = None
    error_message: str | None = None

    @classmethod
    def from_job(cls, job: CatalogImportJob) -> ImportJobResponse:
        return cls(
            job_id=job.job_id,
            store_id=job.store_id,
            status=job.status.value,
            input_type=job.input_type,
            progress=job.progress.model_dump(mode="json"),
            result=job.result.model_dump(mode="json") if job.result else None,
            error_message=job.error_message,
        )


@router.get("/catalog/{sku_id}", response_model=SKUResponse)
async def get_sku(sku_id: str, db: Annotated[FirestoreService, Depends(get_db)]) -> SKUResponse:
    sku = await db.get_sku(sku_id)
    if sku is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SKU not found")
    return SKUResponse(
        sku_id=sku.sku_id,
        name=sku.name,
        description=sku.description,
        category=sku.category,
        price=sku.price,
        currency=sku.currency,
        stock=sku.stock,
        return_rate=sku.return_rate,
        image_url=sku.image_url,
        attributes={k: v for k, v in sku.attributes.items() if not k.startswith("_")},
    )


@router.post("/catalog/import", response_model=ImportJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_import_job(
    body: CreateImportJobRequest,
    claims: Annotated[dict, Depends(require_role(["merchant", "admin"]))],
    db: Annotated[FirestoreService, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportJobResponse:
    require_store_match(claims, body.store_id)

    job = CatalogImportJob(
        job_id=str(uuid.uuid4()),
        store_id=body.store_id,
        initiated_by_uid=claims.get("uid", "unknown"),
        input_type=body.input_type,
        input_source=body.input_source,
        crawl_depth=body.crawl_depth or settings.CRAWL_MAX_DEPTH,
        dry_run=body.dry_run,
        status=ImportStatus.PENDING,
    )
    await db.create_catalog_import_job(job)
    _trigger_cloud_run_job(job, settings)
    return ImportJobResponse.from_job(job)


@router.get("/catalog/import/{job_id}", response_model=ImportJobResponse)
async def get_import_job(
    job_id: str,
    claims: Annotated[dict, Depends(require_role(["merchant", "admin"]))],
    db: Annotated[FirestoreService, Depends(get_db)],
) -> ImportJobResponse:
    job = await db.get_catalog_import_job(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import job not found")
    require_store_match(claims, job.store_id)
    return ImportJobResponse.from_job(job)


def _trigger_cloud_run_job(job: CatalogImportJob, settings: Settings) -> None:
    """Kick off the `catalog-import-runner` Cloud Run Job execution.

    Production: `google.cloud.run_v2.JobsClient.run_job(...)` with
    `--args job_id={job.job_id}` (see `scripts/catalog_import_runner.py`).
    Left as a no-op placeholder in local/dev so this endpoint is exercisable
    without needing a deployed Cloud Run Job -- callers can invoke the
    runner script directly for local end-to-end testing.
    """
    return None
