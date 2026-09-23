"""models/event.py — `events` collection (Implementation Plan §6.1).

Append-only. One document per atomic customer action. Mirrored to BigQuery
via Eventarc (see `services/bigquery.py`, `scripts/bq_mirror_handler.py`).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from models.common import EventType, FirestoreModel, utcnow

# `resolution` valid values by event `type` — Implementation Plan §6.1 table.
RESOLUTION_VALUES_BY_TYPE: dict[EventType, tuple[str, ...]] = {
    EventType.SEARCH: ("exact_match", "near_match", "no_match"),
    EventType.SEARCH_REFINED: ("narrowed", "new_search"),
    EventType.VOICE_SEARCH: ("exact_match", "near_match", "no_match"),
    EventType.FIT_CHECK: ("confirmed", "size_changed", "variant_changed", "abandoned"),
    EventType.FOLLOW_UP_SENT: ("sent",),
    EventType.SUBSTITUTE_ACCEPTED: ("accepted",),
    EventType.RESCUE_DECLINED: ("declined",),
    EventType.STOCKOUT_LOST: ("abandoned",),
    EventType.RETURN_SUBMITTED: ("pending_review",),
    EventType.RETURN_CONFIRMED: ("restock", "refurbish", "liquidate", "hold_for_review"),
}


class Event(FirestoreModel):
    event_id: str
    session_id: str
    user_id: str | None = None
    store_id: str
    platform: str
    type: EventType
    sku_id: str | None = None
    sku_ids: list[str] = Field(default_factory=list)
    matched: bool = False
    score: float | None = None
    resolution: str | None = None
    revenue_at_risk: float = 0.0
    query_text: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

    # Extra, event-type-specific context fields (kept loose — `extra="allow"`
    # on FirestoreModel — so e.g. `detected_language` on voice_search or
    # `prior_result_sku_ids` on search_refined round-trip without a schema
    # migration for every Phase 5A addition).

    def validate_resolution(self) -> None:
        """Raise if `resolution` isn't a value the plan's table permits for `type`."""
        if self.resolution is None:
            return
        allowed = RESOLUTION_VALUES_BY_TYPE.get(self.type, ())
        if self.resolution not in allowed:
            raise ValueError(
                f"resolution={self.resolution!r} is not valid for event type={self.type!r}; "
                f"expected one of {allowed}"
            )


def compute_revenue_at_risk(price: float, matched: bool) -> float:
    """`revenue_at_risk = price * (1 - matched)` — Implementation Plan §6.1.

    A matched search (matched=True) carries zero revenue-at-risk; an
    unmatched one is scored at the full price of the query's closest/most
    relevant SKU as a simple proxy for lost opportunity.
    """
    return round(price * (1 - int(matched)), 2)
