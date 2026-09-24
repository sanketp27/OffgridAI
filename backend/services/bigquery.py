"""services/bigquery.py — BigQuery insert helpers for the `offgrid_events.events` mirror.

Primary write path is Eventarc (Firestore -> BigQuery, automatic — see
`scripts/bq_mirror_handler.py`), so this service is mostly used by that
handler plus ad-hoc analyst queries. Table schema per §6.2:

    event_id STRING, session_id STRING, user_id STRING NULLABLE,
    store_id STRING, platform STRING, type STRING, sku_id STRING NULLABLE,
    sku_ids ARRAY<STRING>, matched BOOL, score FLOAT64 NULLABLE,
    resolution STRING NULLABLE, revenue_at_risk FLOAT64,
    query_text STRING NULLABLE, created_at TIMESTAMP

Partitioned by DATE(created_at), clustered by (store_id, type).

Client-freshness / correctness notes (audited when this file was
integrated into the common/core scaffold): `insert_rows_json` and
`QueryJobConfig`/`ScalarQueryParameter` are still the current, correct
`google-cloud-bigquery` API — no SDK migration needed here. Two real bugs
were fixed instead:
  * `query()` was a *synchronous* method called without `await` from an
    `async def` FastAPI route (`routers/insights.py`), which blocks the
    whole event loop for the duration of the query. It's now `async` and
    offloads the blocking SDK call via `asyncio.to_thread`.
  * Neither method had a retry policy — a single transient
    `ServiceUnavailable`/`TooManyRequests` from BigQuery would surface as
    a 500 to the merchant dashboard. Both now use `core.retry.retry_gcp_call`.
"""

from __future__ import annotations

import asyncio
from typing import Any

from config import Settings
from core.exceptions import BigQueryError, error_boundary
from core.logging import get_logger
from core.retry import retry_gcp_call
from models.event import Event

logger = get_logger(__name__)


class BigQueryService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._project_id = settings.gcp_project_id
        self._dataset = settings.bq_dataset
        self._events_table = settings.bq_events_table
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self._project_id)
        return self._client

    @property
    def events_table_ref(self) -> str:
        return self._settings.bq_events_table_fqn

    def event_to_row(self, event: Event) -> dict[str, Any]:
        """Map an `Event` document to the BigQuery row schema (§6.2)."""
        return {
            "event_id": event.event_id,
            "session_id": event.session_id,
            "user_id": event.user_id,
            "store_id": event.store_id,
            "platform": event.platform,
            "type": event.type.value,
            "sku_id": event.sku_id,
            "sku_ids": event.sku_ids,
            "matched": event.matched,
            "score": event.score,
            "resolution": event.resolution,
            "revenue_at_risk": event.revenue_at_risk,
            "query_text": event.query_text,
            "created_at": event.created_at.isoformat(),
        }

    @retry_gcp_call()
    def insert_event_row(self, event: Event) -> list[dict[str, Any]]:
        """Streaming-insert one Event row. Returns the list of insert errors
        (empty list == success), matching the `insert_rows_json` contract.

        Kept synchronous on purpose — the only caller
        (`scripts/bq_mirror_handler.py`) is a Cloud Functions Gen2 /
        Eventarc CloudEvent handler, which Google Cloud Functions invokes
        synchronously; there's no event loop here to avoid blocking.
        `@retry_gcp_call()` works transparently on sync functions too.
        """
        with error_boundary(
            logger, wrap=BigQueryError, event="bigquery_insert_event_failed",
            message="failed to insert event row", event_id=event.event_id,
        ):
            row = self.event_to_row(event)
            errors: list[dict[str, Any]] = self.client.insert_rows_json(self.events_table_ref, [row])
            if errors:
                logger.error("bigquery_insert_event_rejected", event_id=event.event_id, errors=errors)
            return errors

    @retry_gcp_call()
    async def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Escape hatch for `GET /events/aggregate` and analyst-facing queries.

        Callers should prefer parameterized `sql` (e.g. `@store_id`) with
        `params` over string interpolation — this is the one place in the
        backend where an LLM-driven tool call (Ask-Your-Data merchant
        chat, OG-051) can end up influencing a query's filter values.

        The underlying `google-cloud-bigquery` client is synchronous; the
        blocking call is offloaded to a worker thread via
        `asyncio.to_thread` so this composes cleanly with the rest of the
        async FastAPI app instead of stalling the event loop.
        """
        from google.cloud import bigquery

        with error_boundary(
            logger, wrap=BigQueryError, event="bigquery_query_failed",
            message="BigQuery query failed", sql=sql,
        ):
            job_config = None
            if params:
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter(k, _bq_param_type(v), v)
                        for k, v in params.items()
                    ]
                )

            def _run() -> list[dict[str, Any]]:
                result = self.client.query(sql, job_config=job_config).result()
                return [dict(row) for row in result]

            rows = await asyncio.to_thread(_run)
            logger.debug("bigquery_query_ok", row_count=len(rows))
            return rows


def _bq_param_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT64"
    if isinstance(value, float):
        return "FLOAT64"
    return "STRING"
