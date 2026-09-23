"""models/follow_up_notification.py — `follow_up_notifications` collection (§6.1, OG-050).

Written by the Fit-Check Agent at purchase time. One document per flagged
purchase. Append-only — never updated except for the `delivered` flag flip
on first read (idempotent-safe GET semantics, see routers/fit_check.py).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from models.common import FirestoreModel, utcnow

# Valid `fit_check_resolution` values for a follow-up — "abandoned" never
# generates a follow-up (see trigger rule below).
FOLLOW_UP_ELIGIBLE_RESOLUTIONS = ("confirmed", "size_changed")


class FollowUpNotification(FirestoreModel):
    notification_id: str
    session_id: str
    user_id: str | None = None
    store_id: str
    sku_id: str
    fit_check_resolution: str  # "confirmed" | "size_changed" — never "abandoned"
    follow_up_message: str
    created_at: datetime = Field(default_factory=utcnow)
    delivered: bool = False


def should_generate_follow_up(fit_check_resolution: str) -> bool:
    """Trigger rule (Python): only `confirmed` or `size_changed` generate a follow-up."""
    return fit_check_resolution in FOLLOW_UP_ELIGIBLE_RESOLUTIONS
