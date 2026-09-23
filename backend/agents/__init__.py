"""The OffGrid AI agent mesh (Implementation Plan §8).

All agents are Python classes conforming to the shared `Agent` interface in
`agents.base`. The `Orchestrator` (`agents.orchestrator.Orchestrator`) is
the sole entry point from the FastAPI layer — agents never call each other
directly, only through the Orchestrator, so every cross-agent interaction
stays observable and testable in isolation.
"""
