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
"""

from __future__ import annotations

from typing import Any

from models.event import Event


class BigQueryService:
    def __init__(self, project_id: str, dataset: str, events_table: str = "events") -> None:
        self._project_id = project_id
        self._dataset = dataset
        self._events_table = events_table
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self._project_id)
        return self._client

    @property
    def events_table_ref(self) -> str:
        return f"{self._project_id}.{self._dataset}.{self._events_table}"

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

    def insert_event_row(self, event: Event) -> list[dict[str, Any]]:
        """Streaming-insert one Event row. Returns the list of insert errors
        (empty list == success), matching the `insert_rows_json` contract.
        """
        row = self.event_to_row(event)
        errors: list[dict[str, Any]] = self.client.insert_rows_json(self.events_table_ref, [row])
        return errors

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Escape hatch for `GET /events/aggregate` and analyst-facing queries.

        Callers should prefer parameterized `sql` (e.g. `@store_id`) with
        `params` over string interpolation.
        """
        from google.cloud import bigquery

        job_config = None
        if params:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(k, _bq_param_type(v), v)
                    for k, v in params.items()
                ]
            )
        result = self.client.query(sql, job_config=job_config).result()
        return [dict(row) for row in result]


def _bq_param_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT64"
    if isinstance(value, float):
        return "FLOAT64"
    return "STRING"
