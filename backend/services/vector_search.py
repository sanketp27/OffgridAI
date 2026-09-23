"""services/vector_search.py — VectorSearch client.

Two backends, selected by `settings.vector_search_backend` (never a
hardcoded branch at the call site):

  * "firestore" (MVP, default) — native Firestore vector index on the
    `catalog.embedding` field (`architecture.md`: "Firestore-native for
    MVP; Vertex AI Vector Search for production scale"). Uses
    `Query.find_nearest`.
  * "vertex_ai_vector_search" (production-scale stretch) — a deployed
    Vertex AI Matching Engine index, queried via
    `aiplatform.MatchingEngineIndexEndpoint.find_neighbors`.

Both backends are exposed through the same `VectorSearchClient.search()`
interface so agent code (the Discovery Agent's `vector_search_catalog`
tool) never needs to know which one is active.

Similarity scoring: Firestore's `DistanceMeasure.COSINE` returns a
*distance* (`1 - cosine_similarity`) for each match, not a similarity —
this client converts it back to `similarity = 1 - distance` before
returning, so a caller comparing against
`settings.vector_match_threshold_exact` (0.75) is comparing against the
same "higher is better" scale used throughout the plan (`score >= 0.75`).
Getting this conversion backwards is exactly the kind of bug the
"anti-hallucination" / "numeric accuracy" requirements in the plan are
worried about, so it lives in one place with tests in mind, not
re-implemented at each call site.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from config import Settings, get_settings
from core.exceptions import VectorSearchError, error_boundary
from core.logging import get_logger
from core.retry import retry_gcp_call
from services.firestore_client import FirestoreClient, get_firestore_client

logger = get_logger(__name__)

MatchTier = Literal["exact", "near", "none"]

_DISTANCE_MEASURE_MAP = {
    "cosine": DistanceMeasure.COSINE,
    "euclidean": DistanceMeasure.EUCLIDEAN,
    "dot_product": DistanceMeasure.DOT_PRODUCT,
}


@dataclass(frozen=True, slots=True)
class VectorMatch:
    """One result from a vector similarity search."""

    id: str
    data: dict[str, Any]
    score: float  # similarity, higher = better, roughly in [0, 1] for cosine


class VectorSearchClient:
    """Similarity search over the catalog (or any vector-indexed collection)."""

    def __init__(self, settings: Settings | None = None, firestore: FirestoreClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._firestore = firestore or get_firestore_client()

    def match_tier(self, score: float) -> MatchTier:
        """Classify a similarity score against the configured thresholds.

        `score >= vector_match_threshold_exact` -> "exact" (confident match)
        `score >= vector_match_threshold_near`   -> "near" (weak match / show gap + near-matches)
        otherwise                                -> "none" (honest miss + broadest fallback)
        """
        if score >= self.settings.vector_match_threshold_exact:
            return "exact"
        if score >= self.settings.vector_match_threshold_near:
            return "near"
        return "none"

    # ------------------------------------------------------------------
    # Firestore-native backend (MVP default)
    # ------------------------------------------------------------------

    @retry_gcp_call()
    async def _search_firestore(
        self,
        collection: str,
        vector_field: str,
        query_vector: list[float],
        *,
        top_k: int,
        filters: list[tuple[str, str, Any]] | None,
        distance_measure: str,
    ) -> list[VectorMatch]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        with error_boundary(
            logger, wrap=VectorSearchError, event="vector_search_firestore_failed",
            message="Firestore vector search failed", collection=collection, top_k=top_k,
        ):
            query_ref: Any = self._firestore.raw.collection(collection)
            for field, op, value in filters or []:
                query_ref = query_ref.where(filter=FieldFilter(field, op, value))

            distance_field = "_vector_distance"
            vector_query = query_ref.find_nearest(
                vector_field=vector_field,
                query_vector=Vector(query_vector),
                distance_measure=_DISTANCE_MEASURE_MAP[distance_measure],
                limit=top_k,
                distance_result_field=distance_field,
            )

            matches: list[VectorMatch] = []
            async for doc in vector_query.stream():
                data = doc.to_dict() or {}
                distance = data.pop(distance_field, None)
                # Cosine distance -> cosine similarity. See module docstring.
                similarity = 1.0 - distance if distance is not None else 0.0
                matches.append(VectorMatch(id=doc.id, data=data, score=similarity))
            return matches

    # ------------------------------------------------------------------
    # Vertex AI Vector Search backend (production-scale stretch)
    # ------------------------------------------------------------------

    async def _search_vertex_ai_vector_search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
    ) -> list[VectorMatch]:
        """Query a deployed Vertex AI Matching Engine index.

        Requires `settings.vertex_ai_vector_index_endpoint` and
        `settings.vertex_ai_vector_deployed_index_id`. This is the
        production-scale path called out as a stretch goal in
        `architecture.md` — the Firestore backend above is sufficient for
        the hackathon-scale demo catalog.

        `aiplatform.MatchingEngineIndexEndpoint.find_neighbors` is a
        synchronous SDK call; it's offloaded to a worker thread via
        `asyncio.to_thread` so it doesn't block the event loop.
        """
        import asyncio

        if not self.settings.vertex_ai_vector_index_endpoint or not self.settings.vertex_ai_vector_deployed_index_id:
            raise VectorSearchError(
                "vertex_ai_vector_search backend selected but VERTEX_AI_VECTOR_INDEX_ENDPOINT "
                "/ VERTEX_AI_VECTOR_DEPLOYED_INDEX_ID are not configured",
                code="vector_search_not_configured",
            )

        with error_boundary(
            logger, wrap=VectorSearchError, event="vector_search_vertex_ai_failed",
            message="Vertex AI Vector Search query failed", top_k=top_k,
        ):
            from google.cloud import aiplatform

            def _query() -> Any:
                aiplatform.init(project=self.settings.gcp_project_id, location=self.settings.vertex_ai_location)
                endpoint = aiplatform.MatchingEngineIndexEndpoint(
                    index_endpoint_name=self.settings.vertex_ai_vector_index_endpoint
                )
                return endpoint.find_neighbors(
                    deployed_index_id=self.settings.vertex_ai_vector_deployed_index_id,
                    queries=[query_vector],
                    num_neighbors=top_k,
                )

            neighbors_per_query = await asyncio.to_thread(_query)
            neighbors = neighbors_per_query[0] if neighbors_per_query else []

            matches: list[VectorMatch] = []
            for neighbor in neighbors:
                # Matching Engine returns a distance; for the default
                # DOT_PRODUCT_DISTANCE / COSINE_DISTANCE index configs this
                # is already similarity-like for normalized embeddings, but
                # verify against the specific index's distance metric before
                # comparing to `vector_match_threshold_*` in production.
                matches.append(VectorMatch(id=neighbor.id, data={}, score=float(neighbor.distance)))
            return matches

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        collection: str,
        vector_field: str,
        query_vector: list[float],
        *,
        top_k: int = 5,
        filters: list[tuple[str, str, Any]] | None = None,
        distance_measure: str | None = None,
    ) -> list[VectorMatch]:
        """Run a similarity search against `collection`, using whichever backend is configured."""
        distance_measure = distance_measure or self.settings.vector_search_distance_measure

        if self.settings.vector_search_backend == "firestore":
            return await self._search_firestore(
                collection, vector_field, query_vector,
                top_k=top_k, filters=filters, distance_measure=distance_measure,
            )
        return await self._search_vertex_ai_vector_search(query_vector, top_k=top_k)

    async def search_catalog(
        self,
        query_vector: list[float],
        *,
        category_filter: str | None = None,
        max_price: float | None = None,
        top_k: int = 5,
    ) -> list[VectorMatch]:
        """Search the SKU catalog by embedding similarity, with optional filters.

        Mirrors the Discovery Agent's `vector_search_catalog` function-calling
        tool signature (`backend_implementation_plan.md` §8.2) exactly, so
        the agent's tool implementation can delegate straight to this method.

        `max_price` is applied as a Firestore range filter (`price <= max_price`);
        note Firestore only allows range filters on a single field per query,
        so combining `max_price` with additional range filters elsewhere
        requires a composite index.
        """
        filters: list[tuple[str, str, Any]] = []
        if category_filter:
            filters.append(("category", "==", category_filter))
        if max_price is not None:
            filters.append(("price", "<=", max_price))

        return await self.search(
            self._firestore.collections.catalog,
            self.settings.vector_search_field,
            query_vector,
            top_k=top_k,
            filters=filters,
        )


_client: VectorSearchClient | None = None


def get_vector_search_client() -> VectorSearchClient:
    """Process-wide `VectorSearchClient` singleton (FastAPI-dependency friendly)."""
    global _client
    if _client is None:
        _client = VectorSearchClient()
    return _client
