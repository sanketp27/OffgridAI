"""services/gemini_client.py — Gemini chat/generation client.

Thin wrapper around `google-genai`'s `client.models.generate_content` /
`client.aio.models.generate_content`, used by every interactive agent
(Discovery, Fit-Check, Return Intelligence — `gemini_flash_model`) and the
batch Insight Agent (`gemini_pro_model`). Model names are never passed as
literals from call sites — they come from `Settings`, so swapping models
is a config change, not a code change.

This module intentionally does NOT know about function-calling tool
schemas, system prompts, or grounding rules for any specific agent — that
is application logic and belongs in `agents/*.py`. What it provides is:
  * a configured, retried, logged `generate()` / `generate_async()` call
  * a `generate_structured()` helper for JSON-mode calls (used heavily by
    the Insight Agent's brief generation and the catalog-import extraction
    pipeline, both of which require strict JSON-only output)
"""

from __future__ import annotations

from typing import Any

from google.genai import types as genai_types

from config import Settings, get_settings
from core.exceptions import GeminiError, error_boundary
from core.logging import get_logger
from core.retry import retry_gemini_call
from services._genai_client_factory import get_genai_client

logger = get_logger(__name__)


class GeminiClient:
    """Wrapper around the Gemini Flash / Pro models via `google-genai`."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = get_genai_client(self.settings)

    @property
    def raw(self) -> Any:
        """Escape hatch to the underlying `genai.Client` for calls not wrapped below
        (e.g. multimodal file uploads, live/streaming sessions)."""
        return self._client

    def _resolve_model(self, model: str | None, *, tier: str) -> str:
        if model:
            return model
        return self.settings.gemini_flash_model if tier == "flash" else self.settings.gemini_pro_model

    @retry_gemini_call()
    async def generate(
        self,
        contents: str | list[Any],
        *,
        model: str | None = None,
        tier: str = "flash",
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        response_mime_type: str | None = None,
        response_schema: dict[str, Any] | type | None = None,
    ) -> genai_types.GenerateContentResponse:
        """Call `generate_content` and return the raw SDK response.

        Args:
            contents: A prompt string, or a list of `Content`/parts for
                multimodal (text + image) input.
            model: Explicit model id. Defaults to `settings.gemini_flash_model`
                or `settings.gemini_pro_model` depending on `tier`.
            tier: "flash" (interactive agents) or "pro" (batch Insight Agent).
                Ignored if `model` is given explicitly.
            system_instruction: System prompt for this call.
            tools: Function-calling tool declarations, in `google-genai`'s
                `Tool`/function-declaration shape. Passed through unchanged —
                agent code owns the schema.
            temperature / max_output_tokens: Override the configured defaults.
            response_mime_type / response_schema: Set `response_mime_type="application/json"`
                (optionally with `response_schema`) for structured/JSON-mode output.
                See `generate_structured()` for the common case.
        """
        resolved_model = self._resolve_model(model, tier=tier)

        config = genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature if temperature is not None else self.settings.gemini_default_temperature,
            max_output_tokens=max_output_tokens or self.settings.gemini_default_max_output_tokens,
            tools=tools,
            response_mime_type=response_mime_type,
            response_schema=response_schema,
        )

        with error_boundary(
            logger, wrap=GeminiError, event="gemini_generate_failed",
            message="Gemini generate_content call failed", model=resolved_model,
        ):
            response = await self._client.aio.models.generate_content(
                model=resolved_model,
                contents=contents,
                config=config,
            )
            logger.debug(
                "gemini_generate_ok",
                model=resolved_model,
                candidate_count=len(response.candidates or []),
            )
            return response

    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        """Convenience wrapper: run `generate()` and return the plain text output."""
        response = await self.generate(prompt, **kwargs)
        text = response.text
        if text is None:
            raise GeminiError(
                "Gemini response contained no text (check for a function-call-only response)",
                context={"model": kwargs.get("model") or self._resolve_model(None, tier=kwargs.get("tier", "flash"))},
            )
        return text

    async def generate_structured(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any] | type,
        **kwargs: Any,
    ) -> Any:
        """Run a JSON-mode call and return the parsed object.

        Prefer this over manually setting `response_mime_type="application/json"`
        and parsing the text yourself — it's used anywhere Gemini output must
        be machine-parseable (Insight brief metadata, catalog-import entity
        extraction, structured-intent parsing), which the plan is explicit
        must never silently fail to parse.
        """
        response = await self.generate(
            prompt,
            response_mime_type="application/json",
            response_schema=response_schema,
            **kwargs,
        )
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return parsed

        # Fall back to manual parsing if the SDK didn't populate `.parsed`
        # (e.g. schema was a raw JSON-schema dict rather than a Pydantic type).
        import json

        with error_boundary(
            logger, wrap=GeminiError, event="gemini_json_parse_failed",
            message="Gemini JSON-mode response was not valid JSON",
        ):
            return json.loads(response.text)


_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    """Process-wide `GeminiClient` singleton (FastAPI-dependency friendly)."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
