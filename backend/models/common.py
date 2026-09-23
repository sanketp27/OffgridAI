"""common.py — enums and base classes shared by every model module."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class FirestoreModel(BaseModel):
    """Base class for every Firestore-backed document model.

    Keeps `model_dump(mode="json")` stable for Firestore writes and allows
    unknown fields to round-trip harmlessly (useful when the schema evolves
    across phases without needing a migration step for the hackathon-scale
    dataset).
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class EventType(str, Enum):
    """`events.type` — see Implementation Plan §6.1 `events` collection."""

    SEARCH = "search"
    SEARCH_REFINED = "search_refined"  # OG-048
    VOICE_SEARCH = "voice_search"  # OG-049
    FIT_CHECK = "fit_check"
    FOLLOW_UP_SENT = "follow_up_sent"  # OG-050
    SUBSTITUTE_ACCEPTED = "substitute_accepted"
    RESCUE_DECLINED = "rescue_declined"
    STOCKOUT_LOST = "stockout_lost"
    RETURN_SUBMITTED = "return_submitted"
    RETURN_CONFIRMED = "return_confirmed"


class SignalType(str, Enum):
    """`insights.signal_type` — classified by `agents.insight.classify_signal`."""

    STOCK_GAP = "stock_gap"
    DISCOVERABILITY_GAP = "discoverability_gap"
    SIZING_CONFUSION = "sizing_confusion"
    PRICING_GAP = "pricing_gap"  # OG-052


class ImportStatus(str, Enum):
    """`catalog_import_jobs.status` — one Cloud Run Job run through 4 pipeline stages."""

    PENDING = "pending"
    UPLOADING = "uploading"
    EXTRACTING = "extracting"
    NORMALIZING = "normalizing"
    DEDUPLICATING = "deduplicating"
    EMBEDDING = "embedding"
    WRITING = "writing"
    DONE = "done"
    FAILED = "failed"


class MatchQuality(str, Enum):
    """Derived (never stored) — see §7.2 `match_quality` values."""

    EXACT = "exact"
    NEAR = "near"
    MISS = "miss"


def utcnow() -> datetime:
    """Single source of truth for "now" so tests can monkeypatch it if needed."""
    return datetime.now(UTC)
