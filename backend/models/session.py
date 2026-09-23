"""models/session.py — `sessions` collection (Implementation Plan §6.1)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from models.common import FirestoreModel, utcnow


class StructuredIntent(FirestoreModel):
    """Output of the Discovery Agent's `extract_structured_intent` tool call."""

    category: str
    attributes: dict[str, str] = Field(default_factory=dict)
    budget: float | None = None
    use_case: str | None = None
    urgency: str | None = None
    raw_input_type: str = "text"  # "text" | "image" | "voice"

    def to_embedding_text(self) -> str:
        """Flatten the intent into a single string for Vertex AI Embeddings input."""
        parts = [self.category]
        parts.extend(f"{k}: {v}" for k, v in self.attributes.items())
        if self.use_case:
            parts.append(f"use case: {self.use_case}")
        if self.urgency:
            parts.append(f"urgency: {self.urgency}")
        return ". ".join(parts)


class CartItem(FirestoreModel):
    sku_id: str
    variant_id: str | None = None
    quantity: int = 1
    fit_check_resolution: str | None = None  # "confirmed" | "size_changed" | "abandoned"


class Session(FirestoreModel):
    session_id: str
    platform: str  # "web_widget" | "mobile" | "messaging" | "pos"
    user_id: str | None = None
    store_id: str
    created_at: datetime = Field(default_factory=utcnow)
    last_active_at: datetime = Field(default_factory=utcnow)
    cart: list[CartItem] = Field(default_factory=list)
    intent_history: list[StructuredIntent] = Field(default_factory=list)

    def latest_intent(self) -> StructuredIntent | None:
        return self.intent_history[-1] if self.intent_history else None

    def touch(self) -> None:
        self.last_active_at = utcnow()
