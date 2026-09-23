"""services/embeddings_client.py — Gemini embeddings client.

Wraps `google-genai`'s `client.models.embed_content` (the current,
supported embeddings API for both Vertex AI and the Gemini Developer
API — see `services/_genai_client_factory.py` for why this replaces the
legacy `vertexai.language_models.TextEmbeddingModel`).

Two call sites in the plan drive this client's shape:
  * OG-007 / catalog import Stage 4: `vertex_embeddings.embed_batch(texts,
    model="gemini-embedding-2")` — batches of `embedding_batch_size` (100)
    with a `embedding_batch_sleep_seconds` (0.1s) pause between batches
    "to respect Vertex AI quota" and rate-limit-safe retry per batch.
  * Discovery Agent (OG-013): a single query embedding per shopper search.

Output dimensionality is fixed at `settings.gemini_embedding_dimension`
(768 — must match the Firestore vector index dimension declared in
`architecture.md`) via the embeddings API's `output_dimensionality`
parameter, so every embedding written to `catalog.embedding` and every
query embedding compared against it are the same size by construction.
"""

from __future__ import annotations

from typing import Literal

from google.genai import types as genai_types

from config import Settings, get_settings
from core.exceptions import EmbeddingError, error_boundary
from core.logging import get_logger
from core.retry import retry_gemini_call
from services._genai_client_factory import get_genai_client

logger = get_logger(__name__)

TaskType = Literal[
    "RETRIEVAL_DOCUMENT",  # catalog SKUs — the things being searched over
    "RETRIEVAL_QUERY",  # shopper search text — the thing doing the searching
    "SEMANTIC_SIMILARITY",
    "CLASSIFICATION",
    "CLUSTERING",
]


class EmbeddingsClient:
    """Batched, retried, rate-limit-paced wrapper around Gemini embeddings."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = get_genai_client(self.settings)

    @retry_gemini_call()
    async def _embed_one_batch(
        self,
        texts: list[str],
        *,
        model: str,
        task_type: TaskType,
        output_dimensionality: int,
    ) -> list[list[float]]:
        with error_boundary(
            logger, wrap=EmbeddingError, event="embedding_batch_failed",
            message="Gemini embedding call failed", model=model, batch_size=len(texts),
        ):
            response = await self._client.aio.models.embed_content(
                model=model,
                contents=texts,
                config=genai_types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=output_dimensionality,
                ),
            )
            embeddings = [list(e.values) for e in (response.embeddings or [])]
            if len(embeddings) != len(texts):
                raise EmbeddingError(
                    "embedding count did not match input count",
                    context={"requested": len(texts), "returned": len(embeddings)},
                )
            return embeddings

    async def embed_batch(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int | None = None,
        batch_size: int | None = None,
        pace_between_batches: bool = True,
    ) -> list[list[float]]:
        """Embed a list of texts, chunked into rate-limit-safe batches.

        Preserves input order — `result[i]` is the embedding for `texts[i]`.
        Empty input returns `[]` without making a call.

        Args:
            model: Defaults to `settings.gemini_embedding_model`.
            task_type: "RETRIEVAL_DOCUMENT" for catalog SKUs (default),
                "RETRIEVAL_QUERY" for shopper search text — see `embed_query`.
            output_dimensionality: Defaults to `settings.gemini_embedding_dimension`
                (768) — must match the Firestore vector index dimension.
            batch_size: Defaults to `settings.embedding_batch_size` (100).
            pace_between_batches: Sleep `settings.embedding_batch_sleep_seconds`
                between batches. Disable only in tests.
        """
        if not texts:
            return []

        model = model or self.settings.gemini_embedding_model
        output_dimensionality = output_dimensionality or self.settings.gemini_embedding_dimension
        batch_size = batch_size or self.settings.embedding_batch_size

        results: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            batch_embeddings = await self._embed_one_batch(
                batch, model=model, task_type=task_type, output_dimensionality=output_dimensionality
            )
            results.extend(batch_embeddings)

            is_last_batch = start + batch_size >= len(texts)
            if pace_between_batches and not is_last_batch:
                import asyncio

                await asyncio.sleep(self.settings.embedding_batch_sleep_seconds)

        logger.info("embed_batch_complete", model=model, total_texts=len(texts), batches=(len(texts) + batch_size - 1) // batch_size)
        return results

    async def embed_text(
        self,
        text: str,
        *,
        model: str | None = None,
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int | None = None,
    ) -> list[float]:
        """Embed a single string. Convenience wrapper around `embed_batch([text])`."""
        embeddings = await self.embed_batch(
            [text], model=model, task_type=task_type, output_dimensionality=output_dimensionality,
            pace_between_batches=False,
        )
        return embeddings[0]

    async def embed_query(self, query_text: str, **kwargs: object) -> list[float]:
        """Embed shopper search text for a vector-search lookup (asymmetric `RETRIEVAL_QUERY` embedding)."""
        return await self.embed_text(query_text, task_type="RETRIEVAL_QUERY", **kwargs)  # type: ignore[arg-type]


_client: EmbeddingsClient | None = None


def get_embeddings_client() -> EmbeddingsClient:
    """Process-wide `EmbeddingsClient` singleton (FastAPI-dependency friendly)."""
    global _client
    if _client is None:
        _client = EmbeddingsClient()
    return _client
