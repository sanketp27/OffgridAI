"""agents/orchestrator.py — the Orchestrator (§8.2).

Pure Python routing logic; the Orchestrator never calls an LLM itself. It
deserializes the FastAPI request into an event, loads/saves the Firestore
`Session`, dispatches to the correct specialist agent(s), and returns a
plain-dict payload the router hands back as the HTTP response.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from agents.base import AgentContext
from agents.catalog_import import CatalogImportAgent
from agents.discovery import IntentDiscoveryAgent
from agents.discovery_refinement import DiscoveryRefinementAgent
from agents.fit_check import FitCheckAgent
from agents.insight import InsightAgent
from agents.insight_chat import InsightChatAgent
from agents.return_intel import ReturnIntelligenceAgent
from models.session import Session


class OrchestratorEventType(str, Enum):
    SEARCH = "search"
    FIT_CHECK_RESPONSE = "fit_check_response"
    RETURN = "return"
    INSIGHTS_GENERATE = "insights_generate"
    SEARCH_REFINE = "search_refine"  # OG-048
    VOICE_SEARCH = "voice_search"  # OG-049
    INSIGHTS_CHAT = "insights_chat"  # OG-051
    CATALOG_IMPORT = "catalog_import"  # Phase 5B


# Routing table — §8.2. Kept as a plain dict (not a dispatch-by-string-match
# `if` chain) so the mapping doubles as living documentation of the mesh.
ROUTING: dict[OrchestratorEventType, type] = {
    OrchestratorEventType.SEARCH: IntentDiscoveryAgent,
    OrchestratorEventType.FIT_CHECK_RESPONSE: FitCheckAgent,
    OrchestratorEventType.RETURN: ReturnIntelligenceAgent,
    OrchestratorEventType.INSIGHTS_GENERATE: InsightAgent,
    OrchestratorEventType.SEARCH_REFINE: DiscoveryRefinementAgent,
    OrchestratorEventType.VOICE_SEARCH: IntentDiscoveryAgent,  # same agent, audio_bytes set
    OrchestratorEventType.INSIGHTS_CHAT: InsightChatAgent,
    OrchestratorEventType.CATALOG_IMPORT: CatalogImportAgent,
    # OG-050 follow-up is written by FitCheckAgent inline after
    # fit_check_response; GET /follow-up/{session_id} is a direct Firestore
    # read in routers/fit_check.py — no agent invocation, no routing entry.
    # OG-052 / OG-053 are pipeline extensions inside InsightAgent — no
    # separate routing entry needed.
}


class Orchestrator:
    """Sole entry point from the FastAPI layer into the agent mesh."""

    def __init__(self, context_factory: Any) -> None:
        """`context_factory(store_id, claims) -> AgentContext` — injected so
        the Orchestrator doesn't need direct references to every service
        constructor; `main.py` wires the factory at app startup.
        """
        self._context_factory = context_factory

    async def get_or_create_session(
        self,
        *,
        firestore: Any,
        session_id: str | None,
        store_id: str,
        platform: str,
        user_id: str | None,
    ) -> Session:
        if session_id:
            existing = await firestore.get_session(session_id)
            if existing is not None:
                return existing
        return Session(
            session_id=session_id or str(uuid.uuid4()),
            platform=platform,
            user_id=user_id,
            store_id=store_id,
        )

    async def dispatch(
        self, event_type: OrchestratorEventType, *, store_id: str, claims: dict[str, Any], **kwargs: Any
    ) -> Any:
        agent_cls = ROUTING.get(event_type)
        if agent_cls is None:
            raise ValueError(f"No route registered for event type: {event_type}")

        context: AgentContext = self.build_context(store_id=store_id, claims=claims)
        agent = agent_cls(context)

        if event_type == OrchestratorEventType.VOICE_SEARCH:
            kwargs.setdefault("audio_bytes", kwargs.pop("audio_bytes", None))

        return await agent.run(**kwargs)

    def build_context(self, *, store_id: str, claims: dict[str, Any]) -> AgentContext:
        """Public escape hatch for callers (routers) that need to construct
        an `AgentContext` directly -- e.g. to invoke a single agent method
        like `FitCheckAgent.generate_question` outside the normal
        `dispatch()` event-routing path.
        """
        return self._context_factory(store_id=store_id, claims=claims)  # type: ignore[no-any-return]
