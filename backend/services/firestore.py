"""services/firestore.py — Firestore client + typed CRUD/query helpers.

This is the single place agents and routers talk to Firestore through.
Collection names come from `Settings.firestore_collection_*` (never
hardcoded), set as instance attributes in `__init__` so a rename or a
per-environment namespace only ever touches `.env`. Vector search uses
Firestore's native `find_nearest` (COSINE distance) when available, and
falls back to an in-process numpy cosine-similarity scan — handy against
the Firestore emulator, which does not support vector indexes.

Client-freshness notes (audited when this file was integrated into the
common/core scaffold):
  * Every `.where(...)` call uses the keyword `filter=FieldFilter(...)`
    form. The old positional `.where(field, op, value)` form still works
    on `google-cloud-firestore` 2.x but now raises
    `UserWarning: Detected filter using positional arguments. Prefer
    using the 'filter' keyword argument instead.` on every call — fixed
    throughout this file.
  * The native vector-search path now reads the match distance back via
    `find_nearest(..., distance_result_field=...)` instead of
    re-computing cosine similarity in Python from the returned
    `embedding` field — one Firestore round trip already contains the
    answer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from google.api_core import exceptions as gcp_exceptions
from google.cloud.firestore_v1.base_query import FieldFilter

from config import Settings
from core.exceptions import FirestoreError, error_boundary
from core.logging import get_logger
from core.retry import retry_gcp_call
from models.catalog_import_job import CatalogImportJob
from models.common import EventType
from models.event import Event
from models.follow_up_notification import FollowUpNotification
from models.insight import Insight
from models.merchant_chat_session import MerchantChatSession
from models.return_assessment import ReturnAssessment
from models.session import Session
from models.sku import SKU, SKUSearchResult

logger = get_logger(__name__)

# Firestore errors worth silently falling back to the in-process vector
# scan for (missing/not-yet-provisioned vector index, or emulator that
# doesn't support `find_nearest`). Anything else (permission, quota,
# network) is a real failure and should propagate as a `FirestoreError`
# rather than triggering a full, unindexed collection scan.
_VECTOR_INDEX_UNAVAILABLE_ERRORS = (
    gcp_exceptions.FailedPrecondition,
    gcp_exceptions.InvalidArgument,
    gcp_exceptions.NotFound,
)


class FirestoreService:
    """Async-first wrapper around `google.cloud.firestore.AsyncClient`.

    Construction is cheap and does not touch the network — the underlying
    client is created lazily on first use (`self.client` property) so this
    class is safe to instantiate at import time / in tests without live
    credentials.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._project_id = settings.gcp_project_id
        self._database = settings.firestore_database
        self._client: Any = None

        # Collection names — config-driven (Settings.firestore_collection_*),
        # not hardcoded. Kept as UPPER_CASE instance attributes so call
        # sites (`self.CATALOG`, `db.CATALOG`) read exactly as before.
        self.SESSIONS = settings.firestore_collection_sessions
        self.CATALOG = settings.firestore_collection_catalog
        self.EVENTS = settings.firestore_collection_events
        self.INSIGHTS = settings.firestore_collection_insights
        self.RETURN_ASSESSMENTS = settings.firestore_collection_return_assessments
        self.FOLLOW_UP_NOTIFICATIONS = settings.firestore_collection_follow_up_notifications
        self.MERCHANT_CHAT_SESSIONS = settings.firestore_collection_merchant_chat_sessions
        self.CATALOG_IMPORT_JOBS = settings.firestore_collection_catalog_import_jobs

    @property
    def client(self) -> Any:
        if self._client is None:
            from google.cloud import firestore

            self._client = firestore.AsyncClient(
                project=self._project_id, database=self._database
            )
        return self._client

    # ------------------------------------------------------------------ #
    # Sessions
    # ------------------------------------------------------------------ #
    @retry_gcp_call()
    async def get_session(self, session_id: str) -> Session | None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_get_session_failed",
            message="failed to read session", session_id=session_id,
        ):
            doc = await self.client.collection(self.SESSIONS).document(session_id).get()
            if not doc.exists:
                return None
            return Session.model_validate(doc.to_dict())

    @retry_gcp_call()
    async def save_session(self, session: Session) -> None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_save_session_failed",
            message="failed to write session", session_id=session.session_id,
        ):
            session.touch()
            await self.client.collection(self.SESSIONS).document(session.session_id).set(
                session.model_dump(mode="json")
            )

    # ------------------------------------------------------------------ #
    # Catalog / vector search
    # ------------------------------------------------------------------ #
    @retry_gcp_call()
    async def get_sku(self, sku_id: str) -> SKU | None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_get_sku_failed",
            message="failed to read SKU", sku_id=sku_id,
        ):
            doc = await self.client.collection(self.CATALOG).document(sku_id).get()
            if not doc.exists:
                return None
            return SKU.model_validate(doc.to_dict())

    @retry_gcp_call()
    async def upsert_sku(self, sku: SKU) -> None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_upsert_sku_failed",
            message="failed to write SKU", sku_id=sku.sku_id,
        ):
            sku.updated_at = datetime.now(UTC)
            await self.client.collection(self.CATALOG).document(sku.sku_id).set(
                sku.model_dump(mode="json")
            )

    @retry_gcp_call()
    async def get_all_sku_names(self, store_id: str | None = None) -> set[str]:
        """Used by catalog-import dedup (Stage 3) — exact case-insensitive name match."""
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_scan_sku_names_failed",
            message="failed to scan catalog names", store_id=store_id,
        ):
            query = self.client.collection(self.CATALOG)
            names: set[str] = set()
            async for doc in query.stream():
                data = doc.to_dict()
                names.add(str(data.get("name", "")).lower())
            return names

    async def vector_search_catalog(
        self,
        embedding: list[float],
        *,
        category_filter: str | None = None,
        max_price: float | None = None,
        top_k: int = 5,
    ) -> list[SKUSearchResult]:
        """Top-`top_k` SKUs by cosine similarity to `embedding`, with optional filters.

        Tries Firestore's native vector index first (`find_nearest`); falls
        back to a full in-process cosine scan only when the native path
        fails for an "index not available" reason (not yet provisioned, or
        the emulator, which doesn't support `find_nearest` — see OG-003/
        OG-007). Any other failure (permissions, quota, network) propagates
        as a `FirestoreError` instead of silently degrading to a full scan.
        """
        try:
            return await self._vector_search_native(
                embedding, category_filter=category_filter, max_price=max_price, top_k=top_k
            )
        except _VECTOR_INDEX_UNAVAILABLE_ERRORS as exc:
            logger.warning(
                "vector_index_unavailable_falling_back_to_scan",
                error_type=type(exc).__name__, error_message=str(exc),
            )
            return await self._vector_search_fallback(
                embedding, category_filter=category_filter, max_price=max_price, top_k=top_k
            )

    @retry_gcp_call()
    async def _vector_search_native(
        self,
        embedding: list[float],
        *,
        category_filter: str | None,
        max_price: float | None,
        top_k: int,
    ) -> list[SKUSearchResult]:
        from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
        from google.cloud.firestore_v1.vector import Vector

        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_vector_search_failed",
            message="Firestore native vector search failed", top_k=top_k,
        ):
            query: Any = self.client.collection(self.CATALOG)
            if category_filter:
                query = query.where(filter=FieldFilter("category", "==", category_filter))
            if max_price is not None:
                query = query.where(filter=FieldFilter("price", "<=", max_price))

            distance_field = "_vector_distance"
            vector_query = query.find_nearest(
                vector_field="embedding",
                query_vector=Vector(embedding),
                distance_measure=DistanceMeasure.COSINE,
                limit=top_k,
                distance_result_field=distance_field,
            )
            results: list[SKUSearchResult] = []
            async for doc in vector_query.stream():
                data = doc.to_dict()
                distance = data.pop(distance_field, None)
                sku = SKU.model_validate(data)
                # Firestore's COSINE distance is `1 - cosine_similarity`;
                # convert back so callers compare against
                # VECTOR_MATCH_THRESHOLD_* on a "higher is better" scale.
                score = (1.0 - distance) if distance is not None else 0.0
                results.append(SKUSearchResult(sku=sku, score=score))
            results.sort(key=lambda r: r.score, reverse=True)
            return results

    async def _vector_search_fallback(
        self,
        embedding: list[float],
        *,
        category_filter: str | None,
        max_price: float | None,
        top_k: int,
    ) -> list[SKUSearchResult]:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_vector_fallback_failed",
            message="Firestore fallback vector scan failed", top_k=top_k,
        ):
            query: Any = self.client.collection(self.CATALOG)
            if category_filter:
                query = query.where(filter=FieldFilter("category", "==", category_filter))
            if max_price is not None:
                query = query.where(filter=FieldFilter("price", "<=", max_price))

            scored: list[SKUSearchResult] = []
            async for doc in query.stream():
                sku = SKU.model_validate(doc.to_dict())
                if not sku.embedding:
                    continue
                score = _cosine_similarity(embedding, sku.embedding)
                scored.append(SKUSearchResult(sku=sku, score=score))
            scored.sort(key=lambda r: r.score, reverse=True)
            return scored[:top_k]

    # ------------------------------------------------------------------ #
    # Events (append-only)
    # ------------------------------------------------------------------ #
    @retry_gcp_call()
    async def log_event(self, event: Event) -> None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_log_event_failed",
            message="failed to log event", event_id=event.event_id,
        ):
            event.validate_resolution()
            await self.client.collection(self.EVENTS).document(event.event_id).set(
                event.model_dump(mode="json")
            )

    @retry_gcp_call()
    async def query_events(
        self,
        store_id: str,
        *,
        time_window_days: int | None = None,
        event_type: EventType | None = None,
        category: str | None = None,
    ) -> list[Event]:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_query_events_failed",
            message="failed to query events", store_id=store_id,
        ):
            query: Any = self.client.collection(self.EVENTS).where(
                filter=FieldFilter("store_id", "==", store_id)
            )
            if event_type is not None:
                query = query.where(filter=FieldFilter("type", "==", event_type.value))
            if time_window_days is not None:
                cutoff = datetime.now(UTC) - timedelta(days=time_window_days)
                query = query.where(filter=FieldFilter("created_at", ">=", cutoff))

            events = [Event.model_validate(doc.to_dict()) async for doc in query.stream()]
            # `category` isn't a native Event field (it lives on the SKU) —
            # callers that need category filtering join against the catalog in Python.
            return events

    # ------------------------------------------------------------------ #
    # Insights
    # ------------------------------------------------------------------ #
    @retry_gcp_call()
    async def create_insight(self, insight: Insight) -> None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_create_insight_failed",
            message="failed to write insight", insight_id=insight.insight_id,
        ):
            await self.client.collection(self.INSIGHTS).document(insight.insight_id).set(
                insight.model_dump(mode="json")
            )

    @retry_gcp_call()
    async def get_insights(self, store_id: str, top_n: int | None = None) -> list[Insight]:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_get_insights_failed",
            message="failed to read insights", store_id=store_id,
        ):
            from google.cloud.firestore_v1.query import Query

            query: Any = (
                self.client.collection(self.INSIGHTS)
                .where(filter=FieldFilter("store_id", "==", store_id))
                .order_by("est_revenue_at_risk", direction=Query.DESCENDING)
            )
            if top_n:
                query = query.limit(top_n)
            return [Insight.model_validate(doc.to_dict()) async for doc in query.stream()]

    @retry_gcp_call()
    async def get_insights_by_signal(
        self, store_id: str, signal_type: str, top_n: int = 5
    ) -> list[Insight]:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_get_insights_by_signal_failed",
            message="failed to read insights by signal", store_id=store_id, signal_type=signal_type,
        ):
            query = (
                self.client.collection(self.INSIGHTS)
                .where(filter=FieldFilter("store_id", "==", store_id))
                .where(filter=FieldFilter("signal_type", "==", signal_type))
                .limit(top_n)
            )
            return [Insight.model_validate(doc.to_dict()) async for doc in query.stream()]

    # ------------------------------------------------------------------ #
    # Return assessments
    # ------------------------------------------------------------------ #
    @retry_gcp_call()
    async def create_return_assessment(self, assessment: ReturnAssessment) -> None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_create_return_assessment_failed",
            message="failed to write return assessment", assessment_id=assessment.assessment_id,
        ):
            await self.client.collection(self.RETURN_ASSESSMENTS).document(
                assessment.assessment_id
            ).set(assessment.model_dump(mode="json"))

    @retry_gcp_call()
    async def get_return_assessment(self, assessment_id: str) -> ReturnAssessment | None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_get_return_assessment_failed",
            message="failed to read return assessment", assessment_id=assessment_id,
        ):
            doc = await self.client.collection(self.RETURN_ASSESSMENTS).document(assessment_id).get()
            if not doc.exists:
                return None
            return ReturnAssessment.model_validate(doc.to_dict())

    @retry_gcp_call()
    async def confirm_return_assessment(
        self, assessment_id: str, confirmed_disposition: str, confirmed_by_uid: str
    ) -> None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_confirm_return_assessment_failed",
            message="failed to confirm return assessment", assessment_id=assessment_id,
        ):
            await self.client.collection(self.RETURN_ASSESSMENTS).document(assessment_id).update(
                {
                    "disposition_confirmed": True,
                    "confirmed_disposition": confirmed_disposition,
                    "confirmed_by_uid": confirmed_by_uid,
                    "confirmed_at": datetime.now(UTC),
                }
            )

    async def get_order_history(self, order_id: str, sku_id: str) -> list[dict[str, Any]]:
        """Placeholder order-history lookup.

        The plan does not define a Firestore `orders` collection (order data
        is assumed to live in the merchant's own commerce platform). Replace
        this with a real integration; it returns an empty list so
        `agents.return_intel.compute_return_risk` degrades to "low risk"
        rather than raising when no order system is wired up yet.
        """
        return []

    # ------------------------------------------------------------------ #
    # Follow-up notifications (OG-050)
    # ------------------------------------------------------------------ #
    @retry_gcp_call()
    async def create_follow_up_notification(self, notification: FollowUpNotification) -> None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_create_follow_up_failed",
            message="failed to write follow-up notification", notification_id=notification.notification_id,
        ):
            await self.client.collection(self.FOLLOW_UP_NOTIFICATIONS).document(
                notification.notification_id
            ).set(notification.model_dump(mode="json"))

    @retry_gcp_call()
    async def get_follow_up_for_session(self, session_id: str) -> FollowUpNotification | None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_get_follow_up_failed",
            message="failed to read follow-up notification", session_id=session_id,
        ):
            query = (
                self.client.collection(self.FOLLOW_UP_NOTIFICATIONS)
                .where(filter=FieldFilter("session_id", "==", session_id))
                .limit(1)
            )
            async for doc in query.stream():
                notif = FollowUpNotification.model_validate(doc.to_dict())
                if not notif.delivered:
                    await self.client.collection(self.FOLLOW_UP_NOTIFICATIONS).document(
                        notif.notification_id
                    ).update({"delivered": True})
                return notif
            return None

    # ------------------------------------------------------------------ #
    # Merchant chat sessions (OG-051)
    # ------------------------------------------------------------------ #
    @retry_gcp_call()
    async def get_chat_session(self, chat_session_id: str) -> MerchantChatSession | None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_get_chat_session_failed",
            message="failed to read merchant chat session", chat_session_id=chat_session_id,
        ):
            doc = await self.client.collection(self.MERCHANT_CHAT_SESSIONS).document(
                chat_session_id
            ).get()
            if not doc.exists:
                return None
            return MerchantChatSession.model_validate(doc.to_dict())

    @retry_gcp_call()
    async def save_chat_session(self, session: MerchantChatSession) -> None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_save_chat_session_failed",
            message="failed to write merchant chat session", chat_session_id=session.chat_session_id,
        ):
            await self.client.collection(self.MERCHANT_CHAT_SESSIONS).document(
                session.chat_session_id
            ).set(session.model_dump(mode="json"))

    # ------------------------------------------------------------------ #
    # Catalog import jobs (Phase 5B)
    # ------------------------------------------------------------------ #
    @retry_gcp_call()
    async def create_catalog_import_job(self, job: CatalogImportJob) -> None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_create_import_job_failed",
            message="failed to write catalog import job", job_id=job.job_id,
        ):
            await self.client.collection(self.CATALOG_IMPORT_JOBS).document(job.job_id).set(
                job.model_dump(mode="json")
            )

    @retry_gcp_call()
    async def get_catalog_import_job(self, job_id: str) -> CatalogImportJob | None:
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_get_import_job_failed",
            message="failed to read catalog import job", job_id=job_id,
        ):
            doc = await self.client.collection(self.CATALOG_IMPORT_JOBS).document(job_id).get()
            if not doc.exists:
                return None
            return CatalogImportJob.model_validate(doc.to_dict())

    @retry_gcp_call()
    async def update_catalog_import_job(self, job_id: str, **fields: Any) -> None:
        """Partial update — every pipeline stage calls this to move `status`
        forward and bump `progress` counters. Retried since job-progress
        writes happen frequently during a long-running Cloud Run Job and a
        transient Firestore write failure shouldn't abort the whole import.
        """
        with error_boundary(
            logger, wrap=FirestoreError, event="firestore_update_import_job_failed",
            message="failed to update catalog import job", job_id=job_id,
        ):
            await self.client.collection(self.CATALOG_IMPORT_JOBS).document(job_id).update(fields)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
