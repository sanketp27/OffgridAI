"""agents/insight_chat.py — Insight Agent, Chat mode (§8.2, §7.3, OG-051).

Stateful across turns (loads/saves `MerchantChatSession`). Gemini Pro
answers using ONLY data returned by `CHAT_TOOLS` — the tool implementations
below are the single source of truth for every number the chat can cite.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from agents.base import Agent, AgentContext
from models.common import EventType
from models.merchant_chat_session import ChatSource, ChatTurn, FunctionCallLog, MerchantChatSession

MERCHANT_CHAT_SYSTEM_PROMPT = """
You are OffGrid's Merchant Intelligence assistant. Answer the merchant's question using ONLY
data returned by the available functions.
RULES:
1. Call a function before stating any number. Never state a count, rate, or dollar figure you
   did not receive from a function result.
2. If no function can answer the question, say "I don't have that data" -- do not guess.
3. Cite your sources: for every number, name the function and the key field it came from.
4. Keep answers to 3 sentences maximum. Lead with the finding, not the method.
""".strip()

CHAT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_events_by_filter",
        "description": "Query logged events by type, category, date range.",
        "parameters": {
            "event_type": {"type": "string"},
            "category": {"type": "string", "nullable": True},
            "resolution": {"type": "string", "nullable": True},
            "date_range_days": {"type": "integer", "default": 7},
        },
    },
    {
        "name": "get_fit_check_flip_rate",
        "description": "Return flip rate (size_changed / total fit_checks) per SKU for a category.",
        "parameters": {"category": {"type": "string"}, "date_range_days": {"type": "integer", "default": 7}},
    },
    {
        "name": "get_signal_by_type",
        "description": "Fetch stored Insight documents filtered by signal_type.",
        "parameters": {"signal_type": {"type": "string"}, "top_n": {"type": "integer", "default": 5}},
    },
    {
        "name": "get_top_signals",
        "description": "Return top N insights ranked by est_revenue_at_risk.",
        "parameters": {"top_n": {"type": "integer", "default": 5}},
    },
    {
        "name": "get_sku_details",
        "description": "Fetch a specific SKU's attributes, return_rate, and stock.",
        "parameters": {"sku_id": {"type": "string"}},
    },
]

DECLINE_SIGNALS = ["i don't have", "cannot answer", "no data available", "outside my scope"]


def is_unanswerable(answer: str) -> bool:
    """Python post-processing -- §8.2. Lets the frontend render a distinct
    "can't answer" state rather than a normal answer card.
    """
    lowered = answer.lower()
    return any(signal in lowered for signal in DECLINE_SIGNALS)


@dataclass
class ChatOutcome:
    chat_session_id: str
    answer: str
    sources: list[ChatSource]
    function_calls: list[FunctionCallLog]
    unanswerable: bool


class InsightChatAgent(Agent):
    """A separate class from the batch `InsightAgent` (§8.2) -- stateful
    across turns and uses a different system prompt / tool set.
    """

    name = "insight_chat"

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.model = context.settings.gemini_pro_model
        self._tool_impls = {
            "get_events_by_filter": self._get_events_by_filter,
            "get_fit_check_flip_rate": self._get_fit_check_flip_rate,
            "get_signal_by_type": self._get_signal_by_type,
            "get_top_signals": self._get_top_signals,
            "get_sku_details": self._get_sku_details,
        }

    async def run(  # type: ignore[override]
        self, *, chat_session_id: str | None, message: str
    ) -> ChatOutcome:
        store_id = self.ctx.store_id
        session = None
        if chat_session_id:
            session = await self.ctx.firestore.get_chat_session(chat_session_id)
        if session is None:
            session = MerchantChatSession(
                chat_session_id=chat_session_id or str(uuid.uuid4()),
                store_id=store_id,
                merchant_uid=(self.ctx.claims or {}).get("uid", "unknown"),
            )

        session.append(ChatTurn(role="user", message=message))

        # Production: send MERCHANT_CHAT_SYSTEM_PROMPT + CHAT_TOOLS +
        # session.turns to Gemini Pro, execute whichever function_calls it
        # requests via self._tool_impls, and feed results back for a final
        # synthesis turn. The seam below (`_route_question`) is a
        # deterministic stand-in keyword router so the full plumbing
        # (session persistence, source citation, unanswerable detection) is
        # exercised without live Vertex AI access.
        function_calls: list[FunctionCallLog] = []
        answer, sources = await self._route_question(store_id, message, function_calls)

        unanswerable = is_unanswerable(answer)
        session.append(
            ChatTurn(
                role="assistant", message=answer, function_calls=function_calls, sources=sources
            )
        )
        await self.ctx.firestore.save_chat_session(session)

        return ChatOutcome(
            chat_session_id=session.chat_session_id,
            answer=answer,
            sources=sources,
            function_calls=function_calls,
            unanswerable=unanswerable,
        )

    # ------------------------------------------------------------------ #
    # Query functions (CHAT_TOOLS implementations) — the only place numbers
    # cited in an answer are allowed to originate from.
    # ------------------------------------------------------------------ #
    async def _get_events_by_filter(
        self,
        store_id: str,
        *,
        event_type: str,
        category: str | None = None,
        resolution: str | None = None,
        date_range_days: int = 7,
    ) -> list[dict[str, Any]]:
        events = await self.ctx.firestore.query_events(
            store_id, time_window_days=date_range_days, event_type=EventType(event_type)
        )
        if resolution:
            events = [e for e in events if e.resolution == resolution]
        return [e.model_dump(mode="json") for e in events]

    async def _get_fit_check_flip_rate(
        self, store_id: str, *, category: str, date_range_days: int = 7
    ) -> dict[str, Any]:
        events = await self.ctx.firestore.query_events(
            store_id, time_window_days=date_range_days, event_type=EventType.FIT_CHECK
        )
        by_sku: dict[str, list[str]] = {}
        for e in events:
            if e.sku_id:
                by_sku.setdefault(e.sku_id, []).append(e.resolution or "")

        result: dict[str, Any] = {}
        for sku_id, resolutions in by_sku.items():
            total = len(resolutions)
            flips = sum(1 for r in resolutions if r == "size_changed")
            result[sku_id] = {"flip_rate": round(flips / total, 3) if total else 0.0, "total": total}
        return result

    async def _get_signal_by_type(
        self, store_id: str, *, signal_type: str, top_n: int = 5
    ) -> list[dict[str, Any]]:
        insights = await self.ctx.firestore.get_insights_by_signal(store_id, signal_type, top_n)
        return [i.model_dump(mode="json") for i in insights]

    async def _get_top_signals(self, store_id: str, *, top_n: int = 5) -> list[dict[str, Any]]:
        insights = await self.ctx.firestore.get_insights(store_id, top_n=top_n)
        return [i.model_dump(mode="json") for i in insights]

    async def _get_sku_details(self, store_id: str, *, sku_id: str) -> dict[str, Any] | None:
        sku = await self.ctx.firestore.get_sku(sku_id)
        return sku.model_dump(mode="json") if sku else None

    async def _route_question(
        self, store_id: str, message: str, function_calls: list[FunctionCallLog]
    ) -> tuple[str, list[ChatSource]]:
        """Deterministic stand-in for the Gemini function-calling loop.

        Real implementation: Gemini Pro decides which of `CHAT_TOOLS` to
        call (possibly several), we execute each via `self._tool_impls`,
        log a `FunctionCallLog`, and let Gemini synthesize the final
        3-sentence answer + `ChatSource` list from the results. This stub
        covers the "top signals" case end-to-end as a working example.
        """
        lowered = message.lower()
        if "top" in lowered and ("signal" in lowered or "insight" in lowered):
            insights = await self._get_top_signals(store_id, top_n=3)
            function_calls.append(
                FunctionCallLog(
                    function_name="get_top_signals",
                    arguments={"top_n": 3},
                    result_summary=f"{len(insights)} insights returned",
                )
            )
            if not insights:
                return "I don't have that data yet — no insights have been generated for this store.", []
            top = insights[0]
            sources = [
                ChatSource(
                    source_type="insight",
                    label=f"{top['label']} ({top['signal_type']})",
                    value=top["est_revenue_at_risk"],
                )
            ]
            return (
                f"Your biggest signal right now is \"{top['label']}\" "
                f"({top['signal_type']}), at an estimated ${top['est_revenue_at_risk']:.2f} "
                f"revenue at risk.",
                sources,
            )

        return "I don't have that data — this question isn't covered by the available query functions yet.", []
