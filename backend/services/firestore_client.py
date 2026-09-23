"""services/firestore_client.py — The db client. Async Firestore wrapper + typed CRUD helpers.

This is `services/firestore.py` from the repository layout in the backend
implementation plan ("Firestore client + typed CRUD helpers"). It is the
only place in the codebase that imports `google.cloud.firestore` directly;
every router/agent goes through `FirestoreClient` instead.

Design notes:
  * Async throughout (`firestore.AsyncClient`) — the API layer is FastAPI
    async-first per the plan, and agents `await` Firestore calls alongside
    Gemini calls.
  * Collection *names* are never hardcoded here or at call sites — they
    come from `Settings.firestore_collection_*` and are exposed as typed
    attributes on `FirestoreClient.collections`, so a call like
    `db.collections.events` is both readable and env-configurable.
  * Every method is wrapped in `core.retry.retry_gcp_call` (transient
    Firestore errors — `ServiceUnavailable`, `Aborted` on contested writes,
    etc. — are retried with backoff) and `core.exceptions.error_boundary`
    (failures are logged with a full traceback and re-raised as
    `FirestoreError`, never a bare SDK exception).
  * Generic helpers (`get`, `set`, `add`, `update`, `delete`, `query`)
    operate on `dict[str, Any]` documents, not Pydantic models — model
    (de)serialization is an application-layer concern (`models/*.py`),
    kept out of this common/core layer on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from config import Settings, get_settings
from core.exceptions import FirestoreError, NotFoundError, error_boundary
from core.logging import get_logger
from core.retry import retry_gcp_call

logger = get_logger(__name__)

FilterOp = Literal["==", "!=", "<", "<=", ">", ">=", "in", "not-in", "array-contains", "array-contains-any"]
Filter = tuple[str, FilterOp, Any]


@dataclass(frozen=True, slots=True)
class FirestoreCollections:
    """Typed, config-driven accessors for every collection this backend uses.

    Field names here intentionally mirror `Settings.firestore_collection_*`
    so the mapping from "collection I want" to "env var that names it" is
    obvious. Every value is a plain `str` (the collection name) — callers
    pass it into `FirestoreClient` methods, e.g. `db.get(db.collections.catalog, sku_id)`.
    """

    sessions: str
    catalog: str
    events: str
    insights: str
    return_assessments: str
    follow_up_notifications: str
    merchant_chat_sessions: str
    catalog_import_jobs: str

    @classmethod
    def from_settings(cls, settings: Settings) -> FirestoreCollections:
        return cls(
            sessions=settings.firestore_collection_sessions,
            catalog=settings.firestore_collection_catalog,
            events=settings.firestore_collection_events,
            insights=settings.firestore_collection_insights,
            return_assessments=settings.firestore_collection_return_assessments,
            follow_up_notifications=settings.firestore_collection_follow_up_notifications,
            merchant_chat_sessions=settings.firestore_collection_merchant_chat_sessions,
            catalog_import_jobs=settings.firestore_collection_catalog_import_jobs,
        )


class FirestoreClient:
    """Async Firestore client wrapper with typed CRUD helpers and auto-retry."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.collections = FirestoreCollections.from_settings(self.settings)
        self._client = firestore.AsyncClient(
            project=self.settings.gcp_project_id,
            database=self.settings.firestore_database,
        )

    @property
    def raw(self) -> firestore.AsyncClient:
        """Escape hatch to the underlying SDK client for operations not wrapped below
        (e.g. multi-document transactions spanning several collections)."""
        return self._client

    @staticmethod
    def server_timestamp() -> Any:
        """Sentinel for `created_at`/`updated_at` fields — resolved server-side by Firestore."""
        return firestore.SERVER_TIMESTAMP

    # ------------------------------------------------------------------
    # Single-document operations
    # ------------------------------------------------------------------

    @retry_gcp_call()
    async def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Fetch one document by id. Returns None if it doesn't exist (not an error)."""
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_get_failed",
            message="failed to read document", collection=collection, doc_id=doc_id,
        ):
            snapshot = await self._client.collection(collection).document(doc_id).get()
            if not snapshot.exists:
                return None
            return {**snapshot.to_dict(), "id": snapshot.id}

    async def get_or_raise(self, collection: str, doc_id: str) -> dict[str, Any]:
        """Like `get`, but raises `NotFoundError` instead of returning None."""
        doc = await self.get(collection, doc_id)
        if doc is None:
            raise NotFoundError(
                f"document not found: {collection}/{doc_id}",
                context={"collection": collection, "doc_id": doc_id},
            )
        return doc

    @retry_gcp_call()
    async def set(self, collection: str, doc_id: str, data: dict[str, Any], *, merge: bool = False) -> None:
        """Write a document at a known id, overwriting (or merging) any existing content."""
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_set_failed",
            message="failed to write document", collection=collection, doc_id=doc_id,
        ):
            await self._client.collection(collection).document(doc_id).set(data, merge=merge)
            logger.debug("firestore_set", collection=collection, doc_id=doc_id, merge=merge)

    @retry_gcp_call()
    async def add(self, collection: str, data: dict[str, Any]) -> str:
        """Write a document with an auto-generated id. Returns the new document id."""
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_add_failed",
            message="failed to add document", collection=collection,
        ):
            _, doc_ref = await self._client.collection(collection).add(data)
            logger.debug("firestore_add", collection=collection, doc_id=doc_ref.id)
            return doc_ref.id

    @retry_gcp_call()
    async def update(self, collection: str, doc_id: str, fields: dict[str, Any]) -> None:
        """Partially update an existing document. Raises FirestoreError if it doesn't exist."""
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_update_failed",
            message="failed to update document", collection=collection, doc_id=doc_id,
        ):
            await self._client.collection(collection).document(doc_id).update(fields)
            logger.debug("firestore_update", collection=collection, doc_id=doc_id, fields=list(fields.keys()))

    @retry_gcp_call()
    async def delete(self, collection: str, doc_id: str) -> None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_delete_failed",
            message="failed to delete document", collection=collection, doc_id=doc_id,
        ):
            await self._client.collection(collection).document(doc_id).delete()
            logger.debug("firestore_delete", collection=collection, doc_id=doc_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @retry_gcp_call()
    async def query(
        self,
        collection: str,
        *,
        filters: list[Filter] | None = None,
        order_by: str | None = None,
        descending: bool = False,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Run an equality/range query and return matching documents as dicts (with `id`).

        Example:
            >>> await db.query(
            ...     db.collections.events,
            ...     filters=[("store_id", "==", store_id), ("type", "==", "search")],
            ...     order_by="created_at", descending=True, limit=50,
            ... )
        """
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_query_failed",
            message="failed to query collection", collection=collection, filters=filters,
        ):
            query_ref: Any = self._client.collection(collection)
            for field, op, value in filters or []:
                query_ref = query_ref.where(filter=FieldFilter(field, op, value))
            if order_by:
                direction = firestore.Query.DESCENDING if descending else firestore.Query.ASCENDING
                query_ref = query_ref.order_by(order_by, direction=direction)
            if limit is not None:
                query_ref = query_ref.limit(limit)

            docs = [doc async for doc in query_ref.stream()]
            return [{**doc.to_dict(), "id": doc.id} for doc in docs]

    async def get_all_field_values(self, collection: str, field: str) -> set[Any]:
        """Convenience helper for dedup-style checks, e.g. existing SKU names before a catalog import.

        Streams the whole collection projected to a single field — fine for
        demo/hackathon catalog sizes; swap for a paginated query if the
        collection grows large.
        """
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_field_scan_failed",
            message="failed to scan field values", collection=collection, field=field,
        ):
            query_ref = self._client.collection(collection).select([field])
            values: set[Any] = set()
            async for doc in query_ref.stream():
                data = doc.to_dict() or {}
                if field in data:
                    values.add(data[field])
            return values


@lru_cache
def get_firestore_client() -> FirestoreClient:
    """Process-wide `FirestoreClient` singleton (FastAPI-dependency friendly).

    Usage as a FastAPI dependency:
        >>> def get_db() -> FirestoreClient:
        ...     return get_firestore_client()
    """
    return FirestoreClient()
