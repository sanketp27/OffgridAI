"""agents/base.py — shared agent interface and Gemini client wrapper.

Every specialist agent (Discovery, Fit-Check, Return Intelligence, Insight,
Insight-Chat, Catalog Import) is built as a Google ADK `Agent` subclass in
production. This module defines:

  * `AgentContext`   — the common bundle of services/session/store every
                        agent needs, so `run()` signatures stay consistent.
  * `Agent`           — a minimal structural base (name + model + system
                        prompt + `run()`) that mirrors the ADK `Agent`
                        interface closely enough to swap in `google.adk`'s
                        real base class with a one-line import change once
                        the SDK is wired into a given environment.
  * `GeminiClient`    — one retry-wrapped, function-calling-aware entry
                        point into Vertex AI Gemini, so every agent's
                        prompt-construction code stays separate from the
                        SDK call/retry mechanics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import Settings
from models.session import Session
from services.bigquery import BigQueryService
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService
from services.storage import StorageService

logger = structlog.get_logger(__name__)


@dataclass
class AgentContext:
    """Everything a specialist agent needs to execute one turn.

    Constructed by the Orchestrator per-request; never persisted itself
    (the `session` it carries is the thing that gets persisted).
    """

    settings: Settings
    firestore: FirestoreService
    embeddings: EmbeddingsService
    storage: StorageService
    bigquery: BigQueryService
    store_id: str
    session: Session | None = None
    claims: dict[str, Any] | None = None


class Agent(ABC):
    """Structural base every specialist agent implements.

    Deliberately small: `name`, `model`, and an async `run()`. Concrete
    agents own their own tool schemas and system prompts as module-level
    constants (matching how the Implementation Plan documents them per
    agent) rather than forcing a generic "tools" abstraction here.
    """

    name: str = "agent"
    model: str = ""

    def __init__(self, context: AgentContext) -> None:
        self.ctx = context
        self.gemini = GeminiClient(
            project_id=context.settings.gcp_project_id,
            location=context.settings.vertex_ai_location,
        )
        self.log = logger.bind(agent=self.name)

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute this agent's turn. Concrete signature varies per agent —
        kept as **kwargs here because the Orchestrator dispatches by event
        type with different payload shapes (see agents/orchestrator.py).
        """
        raise NotImplementedError


class GeminiClient:
    """Thin, retry-wrapped wrapper around `vertexai.generative_models.GenerativeModel`.

    Centralizing this means:
      * every agent gets the same `tenacity` backoff policy on Vertex AI
        rate-limit errors (Risk Register §14 — "Vertex AI rate limits
        during demo"), instead of re-implementing retry per agent.
      * function-calling request/response plumbing lives in one place.
    """

    def __init__(self, project_id: str, location: str) -> None:
        self._project_id = project_id
        self._location = location
        self._initialized = False

    def _ensure_init(self) -> None:
        if not self._initialized:
            import vertexai

            vertexai.init(project=self._project_id, location=self._location)
            self._initialized = True

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def generate(
        self,
        *,
        model_name: str,
        system_prompt: str,
        contents: list[Any],
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> Any:
        """Single non-streaming generation call.

        `contents` follows the Gemini content-parts convention (strings,
        `Part.from_data(...)` for images/audio, etc.). `tools`, when
        provided, is translated into a Gemini `FunctionDeclaration` set for
        function-calling agents (Discovery, Fit-Check, Insight-Chat).

        This method intentionally does not attempt to fully abstract every
        Gemini SDK feature — it is the one integration seam every agent
        goes through, kept small enough to unit-test agent *logic* against
        a stub/mock of this method without needing live Vertex AI access.
        """
        self._ensure_init()
        import asyncio

        from vertexai.generative_models import (
            FunctionDeclaration,
            GenerationConfig,
            GenerativeModel,
            Tool,
        )

        gemini_tools = None
        if tools:
            gemini_tools = [
                Tool(
                    function_declarations=[
                        FunctionDeclaration(
                            name=t["name"], description=t.get("description", ""),
                            parameters=t.get("parameters", {}),
                        )
                        for t in tools
                    ]
                )
            ]

        generation_config = None
        if response_schema:
            generation_config = GenerationConfig(
                response_mime_type="application/json", response_schema=response_schema
            )

        model = GenerativeModel(
            model_name, system_instruction=[system_prompt], tools=gemini_tools
        )
        return await asyncio.to_thread(
            model.generate_content, contents, generation_config=generation_config
        )
