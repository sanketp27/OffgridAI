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

Client-freshness note (audited when this file was integrated into the
common/core scaffold): `GeminiClient` used to build on
`vertexai.generative_models.GenerativeModel` / `FunctionDeclaration` /
`Tool` — the generative-AI module set inside `google-cloud-aiplatform`
that Google deprecated on 2025-06-24 and is removing. It's rewritten here
against `google-genai` (`from google import genai`), the current, unified
SDK for both Vertex AI and the public Gemini Developer API. The retry
policy also moved from "retry on any bare `Exception`" (which burns the
retry budget retrying non-retryable errors like a bad request) to
`core.retry.retry_gemini_call`, which only retries transient/rate-limit
errors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from google.genai import types as genai_types

from config import Settings
from core.exceptions import GeminiError, error_boundary
from core.logging import get_logger
from core.retry import retry_gemini_call
from models.session import Session
from services._genai_client_factory import get_genai_client
from services.bigquery import BigQueryService
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService
from services.storage import StorageService

logger = get_logger(__name__)


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
        self.gemini = GeminiClient(context.settings)
        self.log = logger.bind(agent=self.name)

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute this agent's turn. Concrete signature varies per agent —
        kept as **kwargs here because the Orchestrator dispatches by event
        type with different payload shapes (see agents/orchestrator.py).
        """
        raise NotImplementedError


class GeminiClient:
    """Thin, retry-wrapped wrapper around `google-genai`'s `generate_content`.

    Centralizing this means:
      * every agent gets the same backoff policy on Vertex AI rate-limit
        errors (Risk Register §14 — "Vertex AI rate limits during demo"),
        instead of re-implementing retry per agent.
      * function-calling request/response plumbing lives in one place.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = get_genai_client(settings)

    @retry_gemini_call()
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
        `genai.types.Part.from_bytes(data=..., mime_type=...)` for
        images/audio, etc.). `tools`, when provided, is translated into a
        Gemini `FunctionDeclaration` set for function-calling agents
        (Discovery, Fit-Check, Insight-Chat).

        This method intentionally does not attempt to fully abstract every
        Gemini SDK feature — it is the one integration seam every agent
        goes through, kept small enough to unit-test agent *logic* against
        a stub/mock of this method without needing live Vertex AI access.
        """
        gemini_tools = None
        if tools:
            gemini_tools = [
                genai_types.Tool(
                    function_declarations=[
                        genai_types.FunctionDeclaration(
                            name=t["name"],
                            description=t.get("description", ""),
                            parameters=t.get("parameters", {}),
                        )
                        for t in tools
                    ]
                )
            ]

        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=gemini_tools,  # type: ignore[arg-type]  # SDK's ToolListUnion stub is broader than list[Tool]; a plain list[Tool] is valid at runtime.
            temperature=self._settings.gemini_default_temperature,
            max_output_tokens=self._settings.gemini_default_max_output_tokens,
            response_mime_type="application/json" if response_schema else None,
            response_schema=response_schema,
        )

        with error_boundary(
            logger, wrap=GeminiError, event="gemini_generate_failed",
            message="Gemini generate_content call failed", model=model_name,
        ):
            response = await self._client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            logger.debug(
                "gemini_generate_ok",
                model=model_name,
                candidate_count=len(response.candidates or []),
            )
            return response
