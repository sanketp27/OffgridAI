"""services/embeddings.py — Vertex AI Embeddings wrapper.

Used by:
  * Discovery Agent (§8.2) — embed a shopper's structured intent at query time
  * Catalog Import Agent Stage 4 (§8.2, §9.4) — batch-embed new SKUs, 100 per
    call with a 100ms sleep between batches to respect Vertex AI quota
  * scripts/generate_embeddings.py — OG-007 initial catalog embedding
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Iterator, Sequence
from typing import Any, TypeVar

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

T = TypeVar("T")


def chunked(items: Sequence[T], size: int) -> Iterator[list[T]]:
    """Yield `items` in consecutive chunks of at most `size`."""
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


class EmbeddingsService:
    def __init__(
        self,
        project_id: str,
        location: str,
        model_name: str = "gemini-embedding-2",
        *,
        batch_size: int = 100,
        batch_sleep_seconds: float = 0.1,
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._model_name = model_name
        self._batch_size = batch_size
        self._batch_sleep_seconds = batch_sleep_seconds
        self._model: Any = None

    @property
    def model(self) -> Any:
        if self._model is None:
            import vertexai
            from vertexai.language_models import TextEmbeddingModel

            vertexai.init(project=self._project_id, location=self._location)
            self._model = TextEmbeddingModel.from_pretrained(self._model_name)
        return self._model

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def embed_text(self, text: str) -> list[float]:
        """Embed a single string (e.g. a shopper's structured-intent text)."""
        vectors = await asyncio.to_thread(self._embed_texts_sync, [text])
        return vectors[0]

    async def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        """Embed many strings, batched at `batch_size` with a quota-friendly
        sleep between batches — used by the catalog-import Stage 4 writer.
        """
        all_vectors: list[list[float]] = []
        for batch in chunked(list(texts), self._batch_size):
            vectors = await asyncio.to_thread(self._embed_texts_sync, batch)
            all_vectors.extend(vectors)
            if self._batch_sleep_seconds:
                await asyncio.sleep(self._batch_sleep_seconds)
        return all_vectors

    def _embed_texts_sync(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.get_embeddings(texts)
        return [list(e.values) for e in embeddings]
