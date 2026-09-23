"""agents/catalog_import.py — Catalog Import Agent (§8.2, §9.4, Phase 5B).

Runtime: invoked as a Cloud Run Job (`scripts/catalog_import_runner.py`),
not an HTTP service — runs to completion independently of the triggering
`POST /catalog/import` response. Four stages, each updating
`catalog_import_jobs.status`/`progress` in Firestore so the admin dashboard
can poll or `onSnapshot` live progress.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from agents.base import Agent, AgentContext
from config import Settings
from models.catalog_import_job import (
    CatalogImportJob,
    ImportResult,
    RawPage,
    RawProductEntity,
    SKUCandidate,
)
from models.common import ImportStatus
from models.sku import SKU
from services.crawler import Crawler

EXTRACTION_PROMPT = """
You are a product catalog extractor. Read the page content and extract every distinct product
you can identify.

For each product output a JSON object with these fields:
  name (string, required), description (string), price (number), currency (string),
  category_hint (string), attributes (object of key-value pairs),
  image_url (string), stock_hint (number or null)

RULES:
1. Only extract products explicitly mentioned in the page content.
2. If a field is not present in the source, leave it null -- do not infer or guess.
3. If the page contains no products (e.g. it is a blog post or a contact page), return an
   empty array.
4. Do not combine data from multiple products into one entry.

Output: JSON array of product objects.
""".strip()

NORMALIZATION_PROMPT_TEMPLATE = """
Convert this raw product data to our SKU schema. Use ONLY information present in the raw data.

Platform categories (use exactly one): {categories}
Currency (use exactly one): {currencies}

Output a single JSON object:
  sku_id: generate a unique slug from the name (e.g. "heritage-canvas-tote")
  name, description, category, price (float), currency, stock (int, default 0 if unknown),
  return_rate (float, default by category: {return_rate_defaults}),
  attributes (object), image_url (string or null)

RULES:
1. Do not invent a price if none is in the raw data -- set price to null and the validator
   will reject it.
2. return_rate must use the category default shown above unless a specific rate is in the
   raw data.
3. Do not merge attributes from multiple products.
""".strip()

COLUMN_MAPPING_PROMPT = """
Map these columns to SKU fields: name, category, price, stock, attributes, image_url.
Return a JSON mapping {source_column: sku_field | null}.
Only map columns that clearly correspond to a SKU field.
""".strip()

REQUIRED_FIELDS = ("name", "category", "price", "currency")
FIELD_WEIGHTS: dict[str, float] = {
    "name": 0.3,
    "price": 0.25,
    "category": 0.2,
    "image_url": 0.15,
    "description": 0.1,
}


def validate_candidate(candidate: dict[str, Any], *, valid_categories: tuple[str, ...]) -> tuple[bool, str | None]:
    """Stage 3 Python validation (§8.2) — runs after Gemini normalization.

    Returns `(is_valid, error_code)`. Never raises — invalid candidates are
    recorded in `error_details` and the pipeline continues.
    """
    for field_name in REQUIRED_FIELDS:
        if not candidate.get(field_name):
            return False, f"{field_name}_missing"
    if candidate["category"] not in valid_categories:
        return False, "invalid_category"
    price = candidate["price"]
    if not isinstance(price, int | float) or isinstance(price, bool) or price <= 0:
        return False, "invalid_price"
    return True, None


def compute_confidence(candidate: dict[str, Any]) -> float:
    """Stage 3 confidence score (§8.2) — Python formula, never the LLM."""
    return round(
        sum(weight for field_name, weight in FIELD_WEIGHTS.items() if candidate.get(field_name) is not None),
        3,
    )


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"sku-{uuid.uuid4().hex[:8]}"


def deduplicate(
    candidates: list[SKUCandidate], existing_names: set[str]
) -> tuple[list[SKUCandidate], int]:
    """Stage 3 dedup (§8.2) — exact, case-insensitive name match against the
    existing catalog. Returns `(candidates_with_flags_set, skipped_count)`.
    """
    skipped = 0
    for candidate in candidates:
        if candidate.name.lower() in existing_names:
            candidate.is_duplicate = True
            skipped += 1
    return candidates, skipped


class CatalogImportAgent(Agent):
    name = "catalog_import"

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.model = context.settings.gemini_flash_model
        self.crawler = Crawler(
            max_depth=context.settings.CRAWL_MAX_DEPTH,
            max_pages=context.settings.MAX_PAGES_PER_JOB,
            rate_limit_seconds=context.settings.CRAWL_RATE_LIMIT_SECONDS,
            non_product_patterns=context.settings.NON_PRODUCT_URL_PATTERNS,
        )

    async def run(self, *, job: CatalogImportJob) -> CatalogImportJob:  # type: ignore[override]
        try:
            await self._set_status(job.job_id, ImportStatus.UPLOADING)
            raw_pages = await self._ingest(job)

            await self._set_status(job.job_id, ImportStatus.EXTRACTING)
            entities = await self._extract_entities(raw_pages)
            await self.ctx.firestore.update_catalog_import_job(
                job.job_id, **{"progress.raw_entities_found": len(entities)}
            )

            await self._set_status(job.job_id, ImportStatus.NORMALIZING)
            candidates, error_details = await self._normalize_and_validate(entities)

            await self._set_status(job.job_id, ImportStatus.DEDUPLICATING)
            existing_names = await self.ctx.firestore.get_all_sku_names(job.store_id)
            candidates, skipped_duplicates = deduplicate(candidates, existing_names)
            valid_candidates = [c for c in candidates if not c.is_duplicate]

            if job.dry_run:
                await self.ctx.firestore.update_catalog_import_job(
                    job.job_id,
                    status=ImportStatus.DONE.value,
                    **{
                        "progress.skus_normalized": len(candidates),
                        "progress.skus_deduplicated": skipped_duplicates,
                        "progress.skus_invalid": len(error_details),
                    },
                )
                job.status = ImportStatus.DONE
                return job

            await self._set_status(job.job_id, ImportStatus.EMBEDDING)
            added_sku_ids = await self._embed_and_write(valid_candidates, job.store_id)

            result = ImportResult(
                skus_added=len(added_sku_ids),
                skus_skipped_duplicate=skipped_duplicates,
                skus_skipped_invalid=len(error_details),
                sample_sku_ids=added_sku_ids[:5],
                error_details=error_details,
                gcs_report_path=self._write_report(job, added_sku_ids, error_details),
            )
            await self.ctx.firestore.update_catalog_import_job(
                job.job_id,
                status=ImportStatus.DONE.value,
                result=result.model_dump(mode="json"),
                completed_at=datetime.now(UTC),
            )
            job.status = ImportStatus.DONE
            job.result = result
            return job

        except Exception as exc:  # Unrecoverable failure — §9.4 error handling
            await self.ctx.firestore.update_catalog_import_job(
                job.job_id, status=ImportStatus.FAILED.value, error_message=str(exc)
            )
            job.status = ImportStatus.FAILED
            job.error_message = str(exc)
            raise

    async def _set_status(self, job_id: str, status: ImportStatus) -> None:
        await self.ctx.firestore.update_catalog_import_job(job_id, status=status.value)

    # ------------------------------------------------------------------ #
    # Stage 1 — Source Ingestion (Python, branch by input_type)
    # ------------------------------------------------------------------ #
    async def _ingest(self, job: CatalogImportJob) -> list[RawPage]:
        if job.input_type == "url":
            result = await self.crawler.crawl(job.input_source)
            await self.ctx.firestore.update_catalog_import_job(
                job.job_id, **{"progress.pages_crawled": result.pages_crawled}
            )
            return result.pages
        if job.input_type == "pdf":
            return await self._ingest_pdf(job)
        if job.input_type == "image":
            return [RawPage(raw_text="", image_urls=[job.input_source], input_type="image")]
        if job.input_type in ("excel", "csv"):
            return await self._ingest_spreadsheet(job)
        raise ValueError(f"Unsupported input_type: {job.input_type}")

    async def _ingest_pdf(self, job: CatalogImportJob) -> list[RawPage]:
        import fitz  # PyMuPDF

        data = self.ctx.storage.download_bytes(job.input_source)
        doc = fitz.open(stream=data, filetype="pdf")
        pages: list[RawPage] = []
        for page_number, page in enumerate(doc):
            image_urls: list[str] = []
            for image_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                object_path = f"imports/{job.store_id}/{job.job_id}/page_{page_number}_img_{image_index}.{base_image['ext']}"
                self.ctx.storage.upload_bytes(object_path, base_image["image"])
                image_urls.append(object_path)
            pages.append(
                RawPage(
                    source_url=job.input_source,
                    depth=page_number,
                    raw_text=page.get_text(),
                    image_urls=image_urls,
                    input_type="pdf",
                )
            )
        return pages

    async def _ingest_spreadsheet(self, job: CatalogImportJob) -> list[RawPage]:
        import pandas as pd

        data = self.ctx.storage.download_bytes(job.input_source)
        import io

        if job.input_type == "csv":
            df = pd.read_csv(io.BytesIO(data))
        else:
            df = pd.read_excel(io.BytesIO(data))

        # Production: send df.columns + df.head(5) to Gemini Flash with
        # COLUMN_MAPPING_PROMPT and apply the returned mapping. Fallback
        # here: best-effort case-insensitive header match on common SKU
        # field names, so the pipeline runs without a live Gemini call.
        column_map = self._heuristic_column_mapping(list(df.columns))

        pages: list[RawPage] = []
        for _, row in df.iterrows():
            raw_product = {
                sku_field: row[source_col]
                for source_col, sku_field in column_map.items()
                if sku_field and source_col in row and pd.notna(row[source_col])
            }
            pages.append(
                RawPage(raw_text=json.dumps(raw_product, default=str), input_type=job.input_type)
            )
        return pages

    @staticmethod
    def _heuristic_column_mapping(columns: list[str]) -> dict[str, str | None]:
        targets = {
            "name": ("name", "title", "product"),
            "category": ("category", "type"),
            "price": ("price", "cost", "mrp"),
            "stock": ("stock", "quantity", "qty", "inventory"),
            "image_url": ("image", "image_url", "photo"),
        }
        mapping: dict[str, str | None] = {}
        for col in columns:
            normalized = col.strip().lower()
            mapped: str | None = None
            for field_name, keywords in targets.items():
                if any(kw in normalized for kw in keywords):
                    mapped = field_name
                    break
            mapping[col] = mapped
        return mapping

    # ------------------------------------------------------------------ #
    # Stage 2 — Entity Extraction (Gemini Flash, one call per RawPage)
    # ------------------------------------------------------------------ #
    async def _extract_entities(self, pages: list[RawPage]) -> list[RawProductEntity]:
        entities: list[RawProductEntity] = []
        for page in pages:
            page_entities = await self._extract_from_page(page)
            entities.extend(page_entities)
        return entities

    async def _extract_from_page(self, page: RawPage) -> list[RawProductEntity]:
        """One Gemini call (multimodal if `page.image_urls`, else text-only).

        Stubbed to return an empty list (a legitimate, expected outcome per
        the plan: "empty arrays are expected and skipped") so the pipeline
        is runnable end-to-end before Vertex AI access is wired up. Swap
        the body for `self.gemini.generate(..., contents=[...])` using
        EXTRACTION_PROMPT in production.
        """
        if page.input_type in ("excel", "csv") and page.raw_text:
            # Spreadsheet rows are already structured -- no LLM extraction needed.
            try:
                data = json.loads(page.raw_text)
            except json.JSONDecodeError:
                return []
            return [RawProductEntity.model_validate(data)] if data else []
        return []

    # ------------------------------------------------------------------ #
    # Stage 3 — Normalization + Validation (Gemini Flash + Python)
    # ------------------------------------------------------------------ #
    async def _normalize_and_validate(
        self, entities: list[RawProductEntity]
    ) -> tuple[list[SKUCandidate], list[dict[str, Any]]]:
        settings = self.ctx.settings
        candidates: list[SKUCandidate] = []
        errors: list[dict[str, Any]] = []

        for entity in entities:
            normalized = await self._normalize_entity(entity, settings)
            is_valid, error_code = validate_candidate(
                normalized, valid_categories=settings.VALID_SKU_CATEGORIES
            )
            if not is_valid:
                errors.append({"error": error_code, "raw": normalized})
                continue
            candidates.append(
                SKUCandidate(
                    sku_id=normalized.get("sku_id") or slugify(normalized["name"]),
                    name=normalized["name"],
                    description=normalized.get("description", ""),
                    category=normalized["category"],
                    price=float(normalized["price"]),
                    currency=normalized["currency"],
                    stock=int(normalized.get("stock") or 0),
                    return_rate=float(
                        normalized.get("return_rate")
                        or settings.DEFAULT_RETURN_RATE_BY_CATEGORY.get(normalized["category"], 0.05)
                    ),
                    attributes=normalized.get("attributes", {}),
                    image_url=normalized.get("image_url"),
                    confidence=compute_confidence(normalized),
                )
            )
        return candidates, errors

    async def _normalize_entity(
        self, entity: RawProductEntity, settings: Settings
    ) -> dict[str, Any]:
        """Gemini Flash normalization call, per NORMALIZATION_PROMPT_TEMPLATE.

        Stubbed as a best-effort direct field mapping (entity already has
        controlled-vocab-shaped fields in this simplified pipeline) so
        Stage 3's Python validation/confidence logic — the acceptance-
        criteria-bearing part — is independently exercised without a live
        Gemini call. Swap for a real `self.gemini.generate(...)` call using
        `NORMALIZATION_PROMPT_TEMPLATE.format(...)` in production.
        """
        category = entity.category_hint if entity.category_hint in settings.VALID_SKU_CATEGORIES else None
        return {
            "sku_id": slugify(entity.name) if entity.name else None,
            "name": entity.name,
            "description": entity.description or "",
            "category": category or "other",
            "price": entity.price,
            "currency": entity.currency if entity.currency in settings.VALID_CURRENCIES else "USD",
            "stock": entity.stock_hint,
            "return_rate": None,
            "attributes": entity.attributes,
            "image_url": entity.image_url,
        }

    # ------------------------------------------------------------------ #
    # Stage 4 — Embedding + Catalog Write (Python + Vertex AI)
    # ------------------------------------------------------------------ #
    async def _embed_and_write(self, candidates: list[SKUCandidate], store_id: str) -> list[str]:
        texts = [
            f"{c.name}. {c.description}. " + " ".join(f"{k}: {v}" for k, v in c.attributes.items())
            for c in candidates
        ]
        embeddings = await self.ctx.embeddings.embed_batch(texts)

        added_ids: list[str] = []
        for candidate, embedding in zip(candidates, embeddings, strict=True):
            sku = SKU(
                sku_id=candidate.sku_id,
                name=candidate.name,
                description=candidate.description,
                category=candidate.category,
                price=candidate.price,
                currency=candidate.currency,
                stock=candidate.stock,
                return_rate=candidate.return_rate,
                image_url=candidate.image_url or "",
                attributes=candidate.attributes,
                embedding=embedding,
                store_availability={store_id: candidate.stock},
            )
            await self.ctx.firestore.upsert_sku(sku)
            added_ids.append(sku.sku_id)
        return added_ids

    def _write_report(
        self, job: CatalogImportJob, added_sku_ids: list[str], error_details: list[dict[str, Any]]
    ) -> str:
        report_path = self.ctx.storage.import_report_path(job.store_id, job.job_id)
        payload = json.dumps(
            {"job_id": job.job_id, "sku_ids": added_sku_ids, "error_details": error_details},
            default=str,
        ).encode("utf-8")
        return self.ctx.storage.upload_bytes(report_path, payload, content_type="application/json")
