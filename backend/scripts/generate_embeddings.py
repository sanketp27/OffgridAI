"""scripts/generate_embeddings.py — (re)generate embeddings for the whole catalog.

Usage:
    python -m scripts.generate_embeddings [--force]

Run after a bulk `seed_catalog.py --file ... ` (without `--embed`), after a
manual Firestore catalog edit, or whenever `config.Settings.gemini_embedding_model`
changes and every SKU needs re-embedding. `--force` re-embeds SKUs that
already have a vector; without it, only SKUs with an empty `embedding` list
are processed (idempotent incremental runs).
"""

from __future__ import annotations

import argparse
import asyncio

from config import get_settings
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService


async def generate(force: bool) -> None:
    settings = get_settings()
    db = FirestoreService(project_id=settings.gcp_project_id, database=settings.firestore_database)
    embeddings_service = EmbeddingsService(
        project_id=settings.gcp_project_id,
        location=settings.vertex_ai_location,
        model_name=settings.gemini_embedding_model,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
        batch_sleep_seconds=settings.EMBEDDING_BATCH_SLEEP_SECONDS,
    )

    skus = []
    async for doc in db.client.collection(FirestoreService.CATALOG).stream():
        from models.sku import SKU

        sku = SKU.model_validate(doc.to_dict())
        if force or not sku.embedding:
            skus.append(sku)

    if not skus:
        print("No SKUs need embedding (use --force to re-embed everything).")
        return

    print(f"Embedding {len(skus)} SKU(s)...")
    texts = [f"{s.name}. {s.description}. {' '.join(s.attributes.values())}" for s in skus]
    vectors = await embeddings_service.embed_batch(texts)

    for sku, vector in zip(skus, vectors, strict=True):
        sku.embedding = vector
        await db.upsert_sku(sku)
        print(f"  embedded {sku.sku_id}")

    print(f"Done: {len(skus)} SKU(s) embedded.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-embed SKUs that already have a vector")
    args = parser.parse_args()
    asyncio.run(generate(args.force))


if __name__ == "__main__":
    main()
