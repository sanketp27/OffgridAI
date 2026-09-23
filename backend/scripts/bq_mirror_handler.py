"""scripts/bq_mirror_handler.py — Firestore -> BigQuery event mirror (§6.1, §10.2).

Deployed as a Cloud Function (2nd gen) triggered by an Eventarc Firestore
`google.cloud.firestore.document.v1.created` event on the `events`
collection. The Cloud Run Job / Cloud Function runtime calls `handler(cloud_event)`
as its entrypoint (set via `--entry-point=handler` at deploy time).
"""

from __future__ import annotations

from typing import Any

import structlog

from config import get_settings
from models.event import Event
from services.bigquery import BigQueryService

logger = structlog.get_logger(__name__)

_bigquery_service: BigQueryService | None = None


def _get_bigquery_service() -> BigQueryService:
    """Lazy singleton so a warm Cloud Function instance reuses one client
    across invocations instead of reconnecting on every event.
    """
    global _bigquery_service
    if _bigquery_service is None:
        settings = get_settings()
        _bigquery_service = BigQueryService(
            project_id=settings.gcp_project_id,
            dataset=settings.bq_dataset,
            events_table=settings.bq_events_table,
        )
    return _bigquery_service


def handler(cloud_event: Any) -> None:
    """Eventarc entrypoint. `cloud_event.data` carries the Firestore
    `DocumentEventData` protobuf (new document contents under
    `value.fields`); the exact unwrapping below matches the
    `google.events.cloud.firestore.v1.DocumentEventData` shape emitted by
    Firestore-Eventarc triggers.
    """
    document_data = _extract_document_fields(cloud_event)
    if document_data is None:
        logger.warning("bq_mirror_skip_unparseable_event")
        return

    try:
        event = Event.model_validate(document_data)
    except Exception as exc:
        logger.error("bq_mirror_invalid_event_document", error=str(exc), data=document_data)
        return

    bq = _get_bigquery_service()
    errors = bq.insert_event_row(event)
    if errors:
        logger.error("bq_mirror_insert_errors", event_id=event.event_id, errors=errors)
    else:
        logger.info("bq_mirror_insert_ok", event_id=event.event_id)


def _extract_document_fields(cloud_event: Any) -> dict[str, Any] | None:
    """Unwrap the Eventarc `CloudEvent` -> Firestore `DocumentEventData` ->
    plain dict of field values.

    Isolated as its own function (rather than inlined in `handler`) so unit
    tests can feed a plain dict fixture straight through `handler`'s
    downstream logic without constructing a real `CloudEvent`/protobuf.
    """
    try:
        from google.events.cloud.firestore_v1 import DocumentEventData

        firestore_payload = DocumentEventData()
        firestore_payload._pb.ParseFromString(cloud_event.data)
        return _firestore_value_to_dict(firestore_payload.value)
    except ImportError:
        # Local/dev fallback: allow feeding a plain dict directly as
        # `cloud_event.data` (used by the smoke test below and by manual
        # replay tooling), without requiring the `google-events` protobuf
        # package to be installed.
        if isinstance(cloud_event, dict):
            return cloud_event
        data = getattr(cloud_event, "data", None)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _firestore_value_to_dict(document: Any) -> dict[str, Any]:
    """Convert a Firestore `Document` protobuf's `fields` map to a plain
    Python dict, recursively unwrapping the typed `Value` wrapper.
    """
    from google.cloud.firestore_v1._helpers import decode_value  # type: ignore[import-not-found]

    return {k: decode_value(v, None) for k, v in document.fields.items()}
