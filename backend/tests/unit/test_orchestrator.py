"""tests/unit/test_orchestrator.py — routing table completeness/integrity."""

from __future__ import annotations

import pytest

from agents.base import Agent
from agents.orchestrator import ROUTING, Orchestrator, OrchestratorEventType


class TestRoutingTable:
    def test_every_event_type_has_a_route(self) -> None:
        for event_type in OrchestratorEventType:
            assert event_type in ROUTING, f"{event_type} has no registered agent"

    def test_every_routed_agent_is_a_valid_agent_subclass(self) -> None:
        for event_type, agent_cls in ROUTING.items():
            assert issubclass(agent_cls, Agent), f"{agent_cls} for {event_type} isn't an Agent"


class TestDispatchValidation:
    async def test_unknown_event_type_raises(self) -> None:
        orchestrator = Orchestrator(context_factory=lambda **kwargs: None)
        with pytest.raises(ValueError):
            await orchestrator.dispatch("not_a_real_event_type", store_id="s1", claims={})
