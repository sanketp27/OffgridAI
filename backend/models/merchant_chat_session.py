"""models/merchant_chat_session.py — `merchant_chat_sessions` collection (§6.1, OG-051)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from models.common import FirestoreModel, utcnow


class FunctionCallLog(FirestoreModel):
    function_name: str  # e.g. "get_events_by_filter"
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""


class ChatSource(FirestoreModel):
    source_type: str  # "event_aggregate" | "insight" | "sku"
    label: str  # e.g. "fit_check events, footwear, last 7d"
    value: str | float


class ChatTurn(FirestoreModel):
    role: str  # "user" | "assistant"
    message: str
    function_calls: list[FunctionCallLog] = Field(default_factory=list)
    sources: list[ChatSource] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class MerchantChatSession(FirestoreModel):
    chat_session_id: str
    store_id: str
    merchant_uid: str
    created_at: datetime = Field(default_factory=utcnow)
    last_active_at: datetime = Field(default_factory=utcnow)
    turns: list[ChatTurn] = Field(default_factory=list)

    def append(self, turn: ChatTurn) -> None:
        self.turns.append(turn)
        self.last_active_at = utcnow()
