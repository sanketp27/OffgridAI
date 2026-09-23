"""agents/fit_check.py — Fit-Check Agent (§8.2, OG-019..022, OG-050).

Trigger condition and response classification are pure Python (NOT LLM
judgment calls) so they're deterministic and directly unit-testable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from agents.base import Agent, AgentContext
from config import Settings
from models.event import Event, EventType
from models.follow_up_notification import FollowUpNotification, should_generate_follow_up
from models.sku import SKU


# --- Trigger condition (§8.2 OG-019) -------------------------------------
def should_trigger(sku: SKU, *, settings: Settings) -> bool:
    """`sku.category in RETURN_PRONE_CATEGORIES and sku.return_rate > threshold`."""
    return (
        sku.category in settings.RETURN_PRONE_CATEGORIES
        and sku.return_rate > settings.FIT_CHECK_RETURN_RATE_THRESHOLD
    )


# --- Response classification (§8.2) --------------------------------------
RESOLUTION_MAP: dict[str, list[str]] = {
    "size_changed": ["i'll go with", "let me take", "give me the", "i'll take size"],
    "variant_changed": ["different color", "different model", "another colour", "another color"],
    "confirmed": ["i'm good", "that's fine", "yes", "no change", "keep it", "stick with"],
    # "abandoned" is the default when the shopper never responds (timeout) --
    # it deliberately has no keyword list; see classify_response().
}


def classify_response(response_text: str | None) -> str:
    """Classify a shopper's fit-check answer into one of RESOLUTION_MAP's
    keys, or "abandoned" if `response_text` is empty/None (timeout case)
    or matches nothing.
    """
    if not response_text or not response_text.strip():
        return "abandoned"
    text = response_text.lower()
    for resolution, phrases in RESOLUTION_MAP.items():
        if any(phrase in text for phrase in phrases):
            return resolution
    # A response was given but didn't match a known pattern -- default to
    # "confirmed" (the shopper engaged and didn't ask for a change) rather
    # than silently discarding it as abandoned.
    return "confirmed"


# --- Tools (§8.2) ---------------------------------------------------------
FIT_CHECK_TOOLS: list[dict[str, Any]] = [
    {
        "name": "generate_fit_question",
        "description": "Generate one SKU-specific clarifying question about fit or compatibility.",
        "parameters": {
            "sku_id": {"type": "string"},
            "sku_name": {"type": "string"},
            "sku_category": {"type": "string"},
            "return_rate": {"type": "number"},
            "attributes": {"type": "object"},
        },
    },
    {
        "name": "classify_response",
        "description": "Classify shopper's fit-check answer.",
        "parameters": {"response_text": {"type": "string"}, "sku_id": {"type": "string"}},
    },
    {
        "name": "log_fit_check_event",
        "description": "Persist fit-check outcome to Firestore.",
        "parameters": {
            "session_id": {"type": "string"},
            "sku_id": {"type": "string"},
            "question": {"type": "string"},
            "resolution": {"type": "string"},
        },
    },
]

FIT_CHECK_SYSTEM_PROMPT = """
You are OffGrid's Fit-Check Agent. Generate exactly one short, SKU-specific clarifying
question about fit, size, or compatibility for a product known to be return-prone.
Ground the question only in the SKU's real attributes and return_rate. Never invent
sizing facts not present in the SKU data.
""".strip()

# --- Follow-up prompts (§8.2, OG-050) -------------------------------------
FOLLOW_UP_PROMPTS: dict[str, str] = {
    "size_changed": """
Write one short follow-up message (2 sentences max) for a shopper who just swapped from
{original_variant} to {new_variant} for SKU {sku_name}.
Acknowledge the smart choice using only these attributes: {sku_attributes}.
End with a brief easy-return reminder.
Do NOT invent facts about fit, feel, or performance not in the attributes.
""".strip(),
    "confirmed": """
Write one short follow-up message (2 sentences max) for a shopper who confirmed their
original size choice on {sku_name} despite a fit-check prompt.
Reference only these attributes: {sku_attributes}.
Include the store's return window as a confidence safety net.
Do NOT fabricate comfort claims or fit guarantees.
""".strip(),
}


@dataclass
class FitCheckOutcome:
    resolution: str
    event: Event
    follow_up: FollowUpNotification | None
    cart_updated: bool


class FitCheckAgent(Agent):
    name = "fit_check"

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.model = context.settings.gemini_flash_model

    async def generate_question(self, sku: SKU) -> str:
        """OG-020: generate one SKU-specific clarifying question.

        Deterministic fallback template shown here so the agent is usable
        (and testable) without live Vertex AI access; swap the body for a
        real `self.gemini.generate(...)` call using FIT_CHECK_SYSTEM_PROMPT
        + FIT_CHECK_TOOLS in production.
        """
        hint = next(iter(sku.attributes.values()), None)
        if sku.category == "footwear":
            return "This runs about half a size small — do you usually size up?"
        if hint:
            return f"Heads up — this one runs true to {hint}. Still want your usual size?"
        return "This item has a higher-than-average return rate for sizing — sound right for you?"

    async def run(  # type: ignore[override]
        self,
        *,
        session_id: str,
        platform: str,
        user_id: str | None,
        sku_id: str,
        response_text: str | None,
        event_id_from_search: str | None,
        original_variant: str | None = None,
        new_variant: str | None = None,
    ) -> FitCheckOutcome:
        store_id = self.ctx.store_id
        resolution = classify_response(response_text)

        event = Event(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            store_id=store_id,
            platform=platform,
            type=EventType.FIT_CHECK,
            sku_id=sku_id,
            matched=True,
            resolution=resolution,
            query_text=response_text,
        )
        await self.ctx.firestore.log_event(event)

        cart_updated = resolution in ("size_changed", "variant_changed")

        follow_up: FollowUpNotification | None = None
        if should_generate_follow_up(resolution):
            follow_up = await self._generate_follow_up(
                session_id=session_id,
                store_id=store_id,
                user_id=user_id,
                sku_id=sku_id,
                resolution=resolution,
                original_variant=original_variant,
                new_variant=new_variant,
            )

        return FitCheckOutcome(
            resolution=resolution, event=event, follow_up=follow_up, cart_updated=cart_updated
        )

    async def _generate_follow_up(
        self,
        *,
        session_id: str,
        store_id: str,
        user_id: str | None,
        sku_id: str,
        resolution: str,
        original_variant: str | None,
        new_variant: str | None,
    ) -> FollowUpNotification:
        sku = await self.ctx.firestore.get_sku(sku_id)
        sku_name = sku.name if sku else sku_id
        attributes = sku.attributes if sku else {}

        message = self._render_follow_up_message(
            resolution,
            sku_name=sku_name,
            attributes=attributes,
            original_variant=original_variant,
            new_variant=new_variant,
        )

        notification = FollowUpNotification(
            notification_id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            store_id=store_id,
            sku_id=sku_id,
            fit_check_resolution=resolution,
            follow_up_message=message,
        )
        await self.ctx.firestore.create_follow_up_notification(notification)
        return notification

    def _render_follow_up_message(
        self,
        resolution: str,
        *,
        sku_name: str,
        attributes: dict[str, str],
        original_variant: str | None,
        new_variant: str | None,
    ) -> str:
        """Deterministic template rendering of FOLLOW_UP_PROMPTS -- production
        replaces this with a Gemini Flash call using the same prompt text,
        keeping the OG-050 content-differentiation rule intact either way:
        `size_changed` and `confirmed` must produce genuinely different copy.
        """
        attrs_str = ", ".join(f"{k}: {v}" for k, v in attributes.items()) or "no special notes"
        if resolution == "size_changed":
            return (
                f"You swapped from {original_variant or 'your original pick'} to "
                f"{new_variant or 'the new size'} on {sku_name} — a smart call given "
                f"{attrs_str}. If it still feels off after the first wear, our return "
                f"window is open. No rush."
            )
        # resolution == "confirmed"
        return (
            f"You stuck with your original choice on {sku_name} ({attrs_str}). "
            f"If anything feels off once it arrives, easy returns are available within "
            f"the standard window — we've got you covered."
        )
