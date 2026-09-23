"""models/insight.py — `insights` collection (Implementation Plan §6.1)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from models.common import FirestoreModel, SignalType, utcnow


class Insight(FirestoreModel):
    insight_id: str
    store_id: str
    signal_type: SignalType
    label: str  # human-readable cluster label, e.g. "waterproof hiking boots"
    occurrences: int  # computed in Python, never by the LLM
    unique_shoppers: int  # distinct session_ids in the cluster
    trend_pct: float | None = None  # None if insufficient history (first-run case)
    est_revenue_at_risk: float = 0.0  # occurrences * INDUSTRY_CVR * median_aov
    urgency_days: int | None = None  # restock-by-date estimate — stock_gap signals only
    brief: str = ""  # Gemini Pro prose, grounded strictly on the fields above
    recommended_action: str = ""
    generated_at: datetime = Field(default_factory=utcnow)
    event_ids: list[str] = Field(default_factory=list)  # full audit trail
