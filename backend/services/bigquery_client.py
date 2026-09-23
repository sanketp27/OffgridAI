"""services/bigquery_client.py — BigQuery client: insert + query helpers.

Used for two things per the plan:
  * Mirroring `events` documents into `offgrid_events.events` (normally
    driven by the Eventarc trigger automatically, but `insert_events` here
    gives `scripts/bq_mirror_handler.py` — or a manual backfill — a typed,
    retried way to do it directly).
  * Read-only SQL analytics queries for the Insight Agent / Data Analyst
    persona (`query`), always parameterized — never raw string
    interpolation of caller-supplied values, since some of this is
    eventually reachable from the Ask-Your-Data merchant chat feature
    (OG-051), where a filter value could originate from an LLM tool call.

The `google-cloud-bigquery` client is synchronous; every method here
offloads the blocking call to a worker thread via `asyncio.to_thread` so
this client composes cleanly with the rest of the async codebase (FastAPI,
Firestore, Gemini) without blocking the event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any

from google.cloud import bigquery

from config import Settings, get_settings
from core.exceptions import BigQueryError, error_boundary
from core.logging import get_logger
from core.retry import retry_gcp_call

logger = get_logger(__name__)


class BigQueryClient:
    """Insert + query wrapper around `google.cloud.bigquery.Client`."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = bigquery.Client(project=self.settings.gcp_project_id)

    @property
    def raw(self) -> bigquery.Client:
        """Escape hatch to the underlying SDK client (e.g. for load jobs, schema management)."""
        return self._client

    @retry_gcp_call()
    async def insert_rows(self, table_fqn: str, rows: list[dict[str, Any]]) -> None:
        """Stream-insert JSON rows into `project.dataset.table`.

        Uses `insert_rows_json` (the standard streaming-insert path for
        row-at-a-time application events, at this project's volume — see
        the BigQuery Storage Write API instead if this ever needs to
        scale past a few thousand rows/sec). `insert_rows_json` doesn't
        raise on a partial failure — it returns a list of per-row errors —
        so this method checks that list explicitly and raises
        `BigQueryError` if it's non-empty, rather than silently dropping rows.
        """
        if not rows:
            return

        with error_boundary(
            logger, wrap=BigQueryError, event="bigquery_insert_failed",
            message="BigQuery insert failed", table=table_fqn, row_count=len(rows),
        ):
            errors = await asyncio.to_thread(self._client.insert_rows_json, table_fqn, rows)
            if errors:
                raise BigQueryError(
                    "BigQuery rejected one or more rows",
                    context={"table": table_fqn, "errors": errors},
                )
            logger.debug("bigquery_insert_ok", table=table_fqn, row_count=len(rows))

    async def insert_events(self, rows: list[dict[str, Any]]) -> None:
        """Insert rows into the configured events-mirror table (`settings.bq_events_table_fqn`)."""
        await self.insert_rows(self.settings.bq_events_table_fqn, rows)

    @retry_gcp_call()
    async def query(
        self,
        sql: str,
        *,
        params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] | None = None,
        timeout_seconds: float | None = None,
    ) -> list[dict[str, Any]]:
        """Run a parameterized SQL query and return rows as a list of dicts.

        Always pass caller-influenced values via `params`
        (`bigquery.ScalarQueryParameter("store_id", "STRING", store_id)`),
        never f-string them into `sql` — this is the one place in the
        backend where an LLM-driven tool call (Ask-Your-Data chat) can end
        up influencing a query's filter values.

        Example:
            >>> await bq.query(
            ...     "SELECT type, COUNT(*) AS n FROM `project.dataset.events` "
            ...     "WHERE store_id = @store_id AND created_at >= @since GROUP BY type",
            ...     params=[
            ...         bigquery.ScalarQueryParameter("store_id", "STRING", store_id),
            ...         bigquery.ScalarQueryParameter("since", "TIMESTAMP", since),
            ...     ],
            ... )
        """
        with error_boundary(
            logger, wrap=BigQueryError, event="bigquery_query_failed",
            message="BigQuery query failed", sql=sql,
        ):
            job_config = bigquery.QueryJobConfig(query_parameters=params or [])

            def _run() -> list[dict[str, Any]]:
                job = self._client.query(sql, job_config=job_config, timeout=timeout_seconds)
                return [dict(row.items()) for row in job.result()]

            rows = await asyncio.to_thread(_run)
            logger.debug("bigquery_query_ok", row_count=len(rows))
            return rows


_client: BigQueryClient | None = None


def get_bigquery_client() -> BigQueryClient:
    """Process-wide `BigQueryClient` singleton (FastAPI-dependency friendly)."""
    global _client
    if _client is None:
        _client = BigQueryClient()
    return _client
