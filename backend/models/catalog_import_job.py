"""models/catalog_import_job.py — `catalog_import_jobs` collection (§6.1, Phase 5B).

Also defines the intermediate pipeline models (`RawPage`, `RawProductEntity`,
`SKUCandidate`) that flow between the four catalog-import stages described
in §8.2 "Catalog Import Agent" and §9.4 "Catalog Import Flow". These are not
their own Firestore collection — they are ephemeral pipeline state, kept
here so `agents/catalog_import.py` and `services/crawler.py` share one
schema definition.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from models.common import FirestoreModel, ImportStatus, utcnow


class RawPage(FirestoreModel):
    """Output of Stage 1 (Source Ingestion) — one per crawled URL / PDF page /
    uploaded image / spreadsheet row, regardless of `input_type`.
    """

    source_url: str | None = None  # URL input only
    depth: int = 0  # crawl depth level — URL input only
    raw_text: str = ""
    image_urls: list[str] = Field(default_factory=list)
    input_type: str = "url"  # "url" | "pdf" | "image" | "excel" | "csv"


class RawProductEntity(FirestoreModel):
    """Output of Stage 2 (Entity Extraction) — one per product-like entity
    Gemini identified on a `RawPage`. Deliberately loose/optional: Stage 3
    is responsible for controlled-vocabulary normalization + validation.
    """

    name: str | None = None
    description: str | None = None
    price: float | None = None
    currency: str | None = None
    category_hint: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    image_url: str | None = None
    stock_hint: int | None = None
    source_page: str | None = None  # traceability back to the RawPage


class SKUCandidate(FirestoreModel):
    """Output of Stage 3 (Normalization) — validated, ready for Stage 4 embedding+write."""

    sku_id: str
    name: str
    description: str = ""
    category: str
    price: float
    currency: str
    stock: int = 0
    return_rate: float = 0.0
    attributes: dict[str, str] = Field(default_factory=dict)
    image_url: str | None = None
    is_duplicate: bool = False
    confidence: float = 0.0


class ImportProgress(FirestoreModel):
    pages_crawled: int = 0  # URL input only
    raw_entities_found: int = 0
    skus_normalized: int = 0
    skus_deduplicated: int = 0
    skus_invalid: int = 0
    skus_added: int = 0
    embeddings_generated: int = 0


class ImportResult(FirestoreModel):
    skus_added: int = 0
    skus_skipped_duplicate: int = 0
    skus_skipped_invalid: int = 0
    sample_sku_ids: list[str] = Field(default_factory=list)
    error_details: list[dict[str, Any]] = Field(default_factory=list)
    gcs_report_path: str = ""


class CatalogImportJob(FirestoreModel):
    job_id: str
    store_id: str
    initiated_by_uid: str
    input_type: str  # "url" | "pdf" | "image" | "excel" | "csv"
    input_source: str  # URL string, or GCS object path for uploaded files
    crawl_depth: int = 3
    dry_run: bool = False
    status: ImportStatus = ImportStatus.PENDING
    progress: ImportProgress = Field(default_factory=ImportProgress)
    result: ImportResult | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
