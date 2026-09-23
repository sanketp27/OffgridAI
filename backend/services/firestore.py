"""services/firestore.py — Firestore client + typed CRUD/query helpers.

This is the single place agents and routers talk to Firestore through.
Collection names are centralized as class constants so a rename only ever
touches one file. Vector search uses Firestore's native `find_nearest`
(COSINE distance) when available, and falls back to an in-process numpy
cosine-similarity scan — handy against the Firestore emulator, which does
not support vector indexes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential

from models.catalog_import_job import CatalogImportJob
from models.common import EventType
from models.event import Event
from models.follow_up_notification import FollowUpNotification
from models.insight import Insight
from models.merchant_chat_session import MerchantChatSession
from models.return_assessment import ReturnAssessment
from models.session import Session
from models.sku import SKU, SKUSearchResult


class FirestoreService:
    """Async-first wrapper around `google.cloud.firestore.AsyncClient`.

    Construction is cheap and does not touch the network — the underlying
    client is created lazily on first use (`self._client` property) so this
    class is safe to instantiate at import time / in tests without live
    credentials.
    """

    # Collection names — Implementation Plan §6.1
    SESSIONS = "sessions"
    CATALOG = "catalog"
    EVENTS = "events"
    INSIGHTS = "insights"
    RETURN_ASSESSMENTS = "return_assessments"
    FOLLOW_UP_NOTIFICATIONS = "follow_up_notifications"
    MERCHANT_CHAT_SESSIONS = "merchant_chat_sessions"
    CATALOG_IMPORT_JOBS = "catalog_import_jobs"

    def __init__(self, project_id: str, database: str = "(default)") -> None:
        self._project_id = project_id
        self._database = database
        self._client: Any = None

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
    async def get_session(self, session_id: str) -> Session | None:
        doc = await self.client.collection(self.SESSIONS).document(session_id).get()
        if not doc.exists:
            return None
        return Session.model_validate(doc.to_dict())

    async def save_session(self, session: Session) -> None:
        session.touch()
        await self.client.collection(self.SESSIONS).document(session.session_id).set(
            session.model_dump(mode="json")
        )

    # ------------------------------------------------------------------ #
    # Catalog / vector search
    # ------------------------------------------------------------------ #
    async def get_sku(self, sku_id: str) -> SKU | None:
        doc = await self.client.collection(self.CATALOG).document(sku_id).get()
        if not doc.exists:
            return None
        return SKU.model_validate(doc.to_dict())

    async def upsert_sku(self, sku: SKU) -> None:
        sku.updated_at = datetime.now(UTC)
        await self.client.collection(self.CATALOG).document(sku.sku_id).set(
            sku.model_dump(mode="json")
        )

    async def get_all_sku_names(self, store_id: str | None = None) -> set[str]:
        """Used by catalog-import dedup (Stage 3) — exact case-insensitive name match."""
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
        back to a full in-process cosine scan (used against the emulator,
        or any environment where the vector index hasn't been provisioned
        yet — see OG-003/OG-007).
        """
        try:
            return await self._vector_search_native(
                embedding, category_filter=category_filter, max_price=max_price, top_k=top_k
            )
        except Exception:
            return await self._vector_search_fallback(
                embedding, category_filter=category_filter, max_price=max_price, top_k=top_k
            )

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

        query: Any = self.client.collection(self.CATALOG)
        if category_filter:
            query = query.where("category", "==", category_filter)
        if max_price is not None:
            query = query.where("price", "<=", max_price)

        vector_query = query.find_nearest(
            vector_field="embedding",
            query_vector=Vector(embedding),
            distance_measure=DistanceMeasure.COSINE,
            limit=top_k,
        )
        results: list[SKUSearchResult] = []
        async for doc in vector_query.stream():
            data = doc.to_dict()
            sku = SKU.model_validate(data)
            score = _cosine_similarity(embedding, sku.embedding) if sku.embedding else 0.0
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
        query: Any = self.client.collection(self.CATALOG)
        if category_filter:
            query = query.where("category", "==", category_filter)
        if max_price is not None:
            query = query.where("price", "<=", max_price)

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
    async def log_event(self, event: Event) -> None:
        event.validate_resolution()
        await self.client.collection(self.EVENTS).document(event.event_id).set(
            event.model_dump(mode="json")
        )

    async def query_events(
        self,
        store_id: str,
        *,
        time_window_days: int | None = None,
        event_type: EventType | None = None,
        category: str | None = None,
    ) -> list[Event]:
        query: Any = self.client.collection(self.EVENTS).where("store_id", "==", store_id)
        if event_type is not None:
            query = query.where("type", "==", event_type.value)
        if time_window_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=time_window_days)
            query = query.where("created_at", ">=", cutoff)

        events = [Event.model_validate(doc.to_dict()) async for doc in query.stream()]
        # `category` isn't a native Event field (it lives on the SKU) — callers
        # that need category filtering join against the catalog in Python.
        return events

    # ------------------------------------------------------------------ #
    # Insights
    # ------------------------------------------------------------------ #
    async def create_insight(self, insight: Insight) -> None:
        await self.client.collection(self.INSIGHTS).document(insight.insight_id).set(
            insight.model_dump(mode="json")
        )

    async def get_insights(self, store_id: str, top_n: int | None = None) -> list[Insight]:
        query: Any = (
            self.client.collection(self.INSIGHTS)
            .where("store_id", "==", store_id)
            .order_by("est_revenue_at_risk", direction="DESCENDING")
        )
        if top_n:
            query = query.limit(top_n)
        return [Insight.model_validate(doc.to_dict()) async for doc in query.stream()]

    async def get_insights_by_signal(
        self, store_id: str, signal_type: str, top_n: int = 5
    ) -> list[Insight]:
        query = (
            self.client.collection(self.INSIGHTS)
            .where("store_id", "==", store_id)
            .where("signal_type", "==", signal_type)
            .limit(top_n)
        )
        return [Insight.model_validate(doc.to_dict()) async for doc in query.stream()]

    # ------------------------------------------------------------------ #
    # Return assessments
    # ------------------------------------------------------------------ #
    async def create_return_assessment(self, assessment: ReturnAssessment) -> None:
        await self.client.collection(self.RETURN_ASSESSMENTS).document(
            assessment.assessment_id
        ).set(assessment.model_dump(mode="json"))

    async def get_return_assessment(self, assessment_id: str) -> ReturnAssessment | None:
        doc = await self.client.collection(self.RETURN_ASSESSMENTS).document(assessment_id).get()
        if not doc.exists:
            return None
        return ReturnAssessment.model_validate(doc.to_dict())

    async def confirm_return_assessment(
        self, assessment_id: str, confirmed_disposition: str, confirmed_by_uid: str
    ) -> None:
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
    async def create_follow_up_notification(self, notification: FollowUpNotification) -> None:
        await self.client.collection(self.FOLLOW_UP_NOTIFICATIONS).document(
            notification.notification_id
        ).set(notification.model_dump(mode="json"))

    async def get_follow_up_for_session(self, session_id: str) -> FollowUpNotification | None:
        query = (
            self.client.collection(self.FOLLOW_UP_NOTIFICATIONS)
            .where("session_id", "==", session_id)
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
    async def get_chat_session(self, chat_session_id: str) -> MerchantChatSession | None:
        doc = await self.client.collection(self.MERCHANT_CHAT_SESSIONS).document(
            chat_session_id
        ).get()
        if not doc.exists:
            return None
        return MerchantChatSession.model_validate(doc.to_dict())

    async def save_chat_session(self, session: MerchantChatSession) -> None:
        await self.client.collection(self.MERCHANT_CHAT_SESSIONS).document(
            session.chat_session_id
        ).set(session.model_dump(mode="json"))

    # ------------------------------------------------------------------ #
    # Catalog import jobs (Phase 5B)
    # ------------------------------------------------------------------ #
    async def create_catalog_import_job(self, job: CatalogImportJob) -> None:
        await self.client.collection(self.CATALOG_IMPORT_JOBS).document(job.job_id).set(
            job.model_dump(mode="json")
        )

    async def get_catalog_import_job(self, job_id: str) -> CatalogImportJob | None:
        doc = await self.client.collection(self.CATALOG_IMPORT_JOBS).document(job_id).get()
        if not doc.exists:
            return None
        return CatalogImportJob.model_validate(doc.to_dict())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def update_catalog_import_job(self, job_id: str, **fields: Any) -> None:
        """Partial update — every pipeline stage calls this to move `status`
        forward and bump `progress` counters. Retried since job-progress
        writes happen frequently during a long-running Cloud Run Job and a
        transient Firestore write failure shouldn't abort the whole import.
        """
        await self.client.collection(self.CATALOG_IMPORT_JOBS).document(job_id).update(fields)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
