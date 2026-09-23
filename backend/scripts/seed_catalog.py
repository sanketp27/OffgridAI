"""scripts/seed_catalog.py — seed Firestore `catalog` from a local JSON fixture.

Usage:
    python -m scripts.seed_catalog --file catalog_seed.json [--store-id store_001] [--embed]

`catalog_seed.json` is a JSON array of objects matching `models.sku.SKU`
minus `sku_id`/`embedding` (both generated here if absent). Intended for
demo-data bootstrapping (§12) -- NOT the production catalog-import path
(that's `agents.catalog_import.CatalogImportAgent`, run via
`scripts/catalog_import_runner.py`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

from config import get_settings
from models.sku import SKU
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"sku-{uuid.uuid4().hex[:8]}"


async def seed(fixture_path: Path, store_id: str, embed: bool) -> None:
    settings = get_settings()
    db = FirestoreService(project_id=settings.gcp_project_id, database=settings.firestore_database)

    raw_records = json.loads(fixture_path.read_text())
    if not isinstance(raw_records, list):
        print("Fixture file must contain a JSON array of SKU objects.", file=sys.stderr)
        sys.exit(1)

    skus: list[SKU] = []
    for record in raw_records:
        record.setdefault("sku_id", _slugify(record["name"]))
        record.setdefault("store_availability", {store_id: record.get("stock", 0)})
        skus.append(SKU.model_validate(record))

    if embed:
        embeddings_service = EmbeddingsService(
            project_id=settings.gcp_project_id,
            location=settings.vertex_ai_location,
            model_name=settings.gemini_embedding_model,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            batch_sleep_seconds=settings.EMBEDDING_BATCH_SLEEP_SECONDS,
        )
        texts = [f"{s.name}. {s.description}. {' '.join(s.attributes.values())}" for s in skus]
        vectors = await embeddings_service.embed_batch(texts)
        for sku, vector in zip(skus, vectors, strict=True):
            sku.embedding = vector

    for sku in skus:
        await db.upsert_sku(sku)
        print(f"  upserted {sku.sku_id} ({sku.category}, {sku.currency} {sku.price})")

    print(f"Seeded {len(skus)} SKUs into store '{store_id}'" + (" with embeddings." if embed else " (no embeddings -- run scripts/generate_embeddings.py next)."))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="Path to the JSON fixture")
    parser.add_argument("--store-id", default="store_001")
    parser.add_argument("--embed", action="store_true", help="Also generate embeddings inline")
    args = parser.parse_args()

    asyncio.run(seed(args.file, args.store_id, args.embed))


if __name__ == "__main__":
    main()
