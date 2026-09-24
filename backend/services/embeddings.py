"""services/embeddings.py — Gemini Embeddings wrapper.

Used by:
  * Discovery Agent (§8.2) — embed a shopper's structured intent at query time
  * Catalog Import Agent Stage 4 (§8.2, §9.4) — batch-embed new SKUs, 100 per
    call with a 100ms sleep between batches to respect Vertex AI quota
  * scripts/generate_embeddings.py — OG-007 initial catalog embedding

Client-freshness note (audited when this file was integrated into the
common/core scaffold): this used to call
`vertexai.language_models.TextEmbeddingModel`, part of the generative-AI
module set inside `google-cloud-aiplatform` that Google deprecated on
2025-06-24 and is removing. It's rewritten here against `google-genai`
(`from google import genai`), the current, unified SDK for both Vertex AI
and the public Gemini Developer API — see
`services/_genai_client_factory.py` for the shared client construction
this and `agents/base.py`'s `GeminiClient` both use.

Retry note: the previous implementation retried on bare `Exception` —
including non-retryable errors like a bad request or a permissions
failure — which just burns the retry budget on a call that was never
going to succeed. This version retries only on the transient/rate-limit
exceptions in `core.retry.RETRYABLE_EXCEPTIONS`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Iterator, Sequence

from google.genai import types as genai_types

from config import Settings
from core.exceptions import EmbeddingError, error_boundary
from core.logging import get_logger
from core.retry import retry_gemini_call
from services._genai_client_factory import get_genai_client

logger = get_logger(__name__)


def chunked[T](items: Sequence[T], size: int) -> Iterator[list[T]]:
    """Yield `items` in consecutive chunks of at most `size`."""
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


class EmbeddingsService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model_name = settings.gemini_embedding_model
        self._output_dimensionality = settings.embedding_dimensions
        self._batch_size = settings.EMBEDDING_BATCH_SIZE
        self._batch_sleep_seconds = settings.EMBEDDING_BATCH_SLEEP_SECONDS
        self._client = get_genai_client(settings)

    @retry_gemini_call()
    async def _embed_batch_call(self, texts: list[str], *, task_type: str) -> list[list[float]]:
        with error_boundary(
            logger, wrap=EmbeddingError, event="embedding_call_failed",
            message="Gemini embedding call failed", model=self._model_name, batch_size=len(texts),
        ):
            response = await self._client.aio.models.embed_content(
                model=self._model_name,
                contents=texts,
                config=genai_types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self._output_dimensionality,
                ),
            )
            vectors = [list(e.values or []) for e in (response.embeddings or [])]
            if len(vectors) != len(texts):
                raise EmbeddingError(
                    "embedding count did not match input count",
                    context={"requested": len(texts), "returned": len(vectors)},
                )
            return vectors

    async def embed_text(self, text: str, *, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
        """Embed a single string (e.g. a shopper's structured-intent text).

        Defaults to the "RETRIEVAL_QUERY" task type — this method's callers
        (Discovery Agent, at query time) are embedding the *search* side of
        an asymmetric retrieval pair; catalog SKUs are embedded with
        `embed_batch(..., task_type="RETRIEVAL_DOCUMENT")` (the default),
        which the embedding model optimizes for differently.
        """
        vectors = await self._embed_batch_call([text], task_type=task_type)
        return vectors[0]

    async def embed_batch(
        self, texts: Iterable[str], *, task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        """Embed many strings, batched at `batch_size` with a quota-friendly
        sleep between batches — used by the catalog-import Stage 4 writer.

        Defaults to "RETRIEVAL_DOCUMENT" — the catalog side of the
        asymmetric retrieval pair (see `embed_text`).
        """
        all_vectors: list[list[float]] = []
        batches = list(chunked(list(texts), self._batch_size))
        for i, batch in enumerate(batches):
            vectors = await self._embed_batch_call(batch, task_type=task_type)
            all_vectors.extend(vectors)
            is_last = i == len(batches) - 1
            if self._batch_sleep_seconds and not is_last:
                await asyncio.sleep(self._batch_sleep_seconds)
        logger.info("embed_batch_complete", total_texts=len(all_vectors), batches=len(batches))
        return all_vectors
