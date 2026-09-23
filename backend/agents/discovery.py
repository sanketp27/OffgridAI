"""agents/discovery.py — Intent + Discovery Agent (§8.2).

Covers OG-012 (structured-intent extraction) through OG-018
(anti-hallucination suite), plus the OG-049 voice/multilingual extension
(same agent, `audio_bytes` parameter — no new file per the plan).

Execution flow (§9.1):
    1. extract_structured_intent (Gemini function-calling)              [OG-012]
    2. embed(intent.to_embedding_text())                                [Vertex AI Embeddings]
    3. vector_search_catalog(embedding, filters)                        [OG-013]
    4. match-quality threshold routing                                  [OG-014]
    5. grounded, per-result explanation generation                      [OG-015]
    6. log_search_event (fire-and-forget)                               [OG-017]
    7. FitCheck trigger check on the top result
    8. return SearchResponse
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from agents.base import Agent, AgentContext
from models.common import MatchQuality
from models.event import Event, EventType, compute_revenue_at_risk
from models.session import Session, StructuredIntent
from models.sku import SKUSearchResult

# --- Gemini function-calling tool schema (§8.2) --------------------------
DISCOVERY_TOOLS: list[dict[str, Any]] = [
    {
        "name": "extract_structured_intent",
        "description": "Parse free-form text or image into a structured shopping intent.",
        "parameters": {
            "category": {"type": "string"},
            "attributes": {"type": "object"},
            "budget": {"type": "number", "nullable": True},
            "use_case": {"type": "string", "nullable": True},
            "urgency": {"type": "string", "nullable": True},
        },
    },
    {
        "name": "vector_search_catalog",
        "description": "Search the SKU catalog by embedding similarity with optional filters.",
        "parameters": {
            "embedding": {"type": "array", "items": {"type": "number"}},
            "category_filter": {"type": "string", "nullable": True},
            "max_price": {"type": "number", "nullable": True},
            "top_k": {"type": "integer", "default": 5},
        },
    },
    {
        "name": "log_search_event",
        "description": "Persist the search event to Firestore.",
        "parameters": {
            "session_id": {"type": "string"},
            "matched": {"type": "boolean"},
            "score": {"type": "number"},
            "sku_ids": {"type": "array", "items": {"type": "string"}},
            "query_text": {"type": "string"},
        },
    },
]

DISCOVERY_SYSTEM_PROMPT = """
You are OffGrid's Discovery Agent. Your only job is to understand what a shopper wants and
return the most relevant products from the catalog.

STRICT RULES:
1. You may only describe products retrieved by vector_search_catalog. Never mention features,
   colors, or attributes not present in a retrieved SKU's data.
2. If no strong match exists, explain the gap honestly and show the closest available products.
3. Never return an empty result -- always show something with an explanation.
4. After retrieving results, call log_search_event before returning.
""".strip()

VOICE_INTENT_PROMPT = """
You will receive an audio clip of a shopper search query.
1. Transcribe it exactly in the original language.
2. Detect the BCP-47 language code.
3. Extract structured intent as JSON: {category, attributes, budget, use_case, urgency}.
4. Do NOT translate to English. The category must still be one of our defined categories.

After this step, all result explanations must be generated in the same detected language.
""".strip()


@dataclass
class SearchOutcome:
    session: Session
    intent: StructuredIntent
    results: list[SKUSearchResult]
    match_quality: MatchQuality
    event: Event
    fit_check_triggered: bool
    fit_check_sku_id: str | None
    detected_language: str | None = None
    transcription: str | None = None


def classify_match_quality(
    top_score: float, *, exact_threshold: float, near_threshold: float
) -> MatchQuality:
    """Score threshold routing — §7.2 `match_quality`, §9.1 step 4.

    score >= exact_threshold        -> exact
    near_threshold <= score < exact -> near
    score < near_threshold          -> miss
    """
    if top_score >= exact_threshold:
        return MatchQuality.EXACT
    if top_score >= near_threshold:
        return MatchQuality.NEAR
    return MatchQuality.MISS


class IntentDiscoveryAgent(Agent):
    name = "discovery"

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.model = context.settings.gemini_flash_model

    async def run(  # type: ignore[override]
        self,
        *,
        session: Session,
        query_text: str | None = None,
        image_bytes: bytes | None = None,
        audio_bytes: bytes | None = None,
        language_hint: str | None = None,
        category_filter: str | None = None,
    ) -> SearchOutcome:
        settings = self.ctx.settings
        detected_language: str | None = None
        transcription: str | None = None

        # --- Step 1: structured intent extraction ---------------------- #
        if audio_bytes is not None:
            # OG-049: single multimodal call transcribes + detects language +
            # extracts intent in one round-trip -- no separate translation step.
            intent, detected_language, transcription = await self._extract_intent_from_audio(
                audio_bytes, language_hint
            )
        else:
            intent = await self._extract_intent(query_text=query_text, image_bytes=image_bytes)

        session.intent_history.append(intent)

        # --- Step 2: embed the intent ----------------------------------- #
        query_vector = await self.ctx.embeddings.embed_text(intent.to_embedding_text())

        # --- Step 3: vector search --------------------------------------- #
        results = await self.ctx.firestore.vector_search_catalog(
            query_vector,
            category_filter=category_filter or intent.category,
            max_price=intent.budget,
            top_k=settings.SEARCH_TOP_K,
        )
        if not results:
            # §8.2 rule 3: "Never return an empty result" -- broaden the
            # fallback by dropping category/price filters and retry once.
            results = await self.ctx.firestore.vector_search_catalog(
                query_vector, top_k=settings.SEARCH_TOP_K
            )

        top_score = results[0].score if results else 0.0
        match_quality = classify_match_quality(
            top_score,
            exact_threshold=settings.VECTOR_MATCH_THRESHOLD_EXACT,
            near_threshold=settings.VECTOR_MATCH_THRESHOLD_NEAR,
        )
        matched = match_quality == MatchQuality.EXACT

        # --- Step 5: grounded explanations (OG-015) ---------------------- #
        for result in results:
            result.sku.attributes.setdefault(
                "_match_explanation",
                self._grounded_explanation(result, intent, language=detected_language),
            )

        # --- Step 6: log the search event (OG-017) ----------------------- #
        event = Event(
            event_id=str(uuid.uuid4()),
            session_id=session.session_id,
            user_id=session.user_id,
            store_id=session.store_id,
            platform=session.platform,
            type=EventType.VOICE_SEARCH if audio_bytes else EventType.SEARCH,
            sku_ids=[r.sku.sku_id for r in results],
            matched=matched,
            score=top_score,
            resolution=_resolution_for_quality(match_quality),
            revenue_at_risk=compute_revenue_at_risk(
                results[0].sku.price if results else 0.0, matched
            ),
            query_text=query_text or transcription,
        )
        if detected_language:
            event.model_extra["detected_language"] = detected_language  # type: ignore[union-attr]
        await self.ctx.firestore.log_event(event)
        await self.ctx.firestore.save_session(session)

        # --- Step 7: Fit-Check trigger check on the top result ----------- #
        fit_check_triggered = False
        fit_check_sku_id: str | None = None
        if results:
            from agents.fit_check import should_trigger

            top_sku = results[0].sku
            if should_trigger(top_sku, settings=settings):
                fit_check_triggered = True
                fit_check_sku_id = top_sku.sku_id

        return SearchOutcome(
            session=session,
            intent=intent,
            results=results,
            match_quality=match_quality,
            event=event,
            fit_check_triggered=fit_check_triggered,
            fit_check_sku_id=fit_check_sku_id,
            detected_language=detected_language,
            transcription=transcription,
        )

    # ---------------------------------------------------------------- #
    # Gemini call sites — isolated so they're easy to mock in tests
    # ---------------------------------------------------------------- #
    async def _extract_intent(
        self, *, query_text: str | None, image_bytes: bytes | None
    ) -> StructuredIntent:
        contents: list[Any] = []
        if query_text:
            contents.append(query_text)
        if image_bytes:
            contents.append(image_bytes)  # production: wrap via Part.from_data(...)

        response = await self.gemini.generate(
            model_name=self.model,
            system_prompt=DISCOVERY_SYSTEM_PROMPT,
            contents=contents,
            tools=DISCOVERY_TOOLS,
        )
        return self._parse_intent_response(response)

    async def _extract_intent_from_audio(
        self, audio_bytes: bytes, language_hint: str | None
    ) -> tuple[StructuredIntent, str, str]:
        response = await self.gemini.generate(
            model_name=self.model,
            system_prompt=VOICE_INTENT_PROMPT,
            contents=[audio_bytes],  # production: Part.from_data(audio_bytes, mime_type=...)
        )
        parsed = self._parse_voice_response(response)
        return parsed["intent"], parsed.get("detected_language", "und"), parsed["transcription"]

    def _grounded_explanation(
        self, result: SKUSearchResult, intent: StructuredIntent, *, language: str | None
    ) -> str:
        """Placeholder deterministic explanation, grounded only in retrieved
        SKU attributes -- swapped for a real Gemini call in production
        (OG-015). Kept as a pure function here so `test_discovery.py` can
        assert on grounding without hitting Vertex AI.
        """
        attrs = ", ".join(f"{k} {v}" for k, v in result.sku.attributes.items() if not k.startswith("_"))
        return f"{result.sku.name} matches your search ({attrs})." if attrs else result.sku.name

    @staticmethod
    def _parse_intent_response(response: Any) -> StructuredIntent:
        """Extract the `extract_structured_intent` function-call args from a
        Gemini response. Production implementation reads
        `response.candidates[0].function_calls`; left as a narrow seam so
        tests can monkeypatch `GeminiClient.generate` and feed a fixture
        dict straight through instead of a live SDK response object.
        """
        if isinstance(response, dict):
            return StructuredIntent.model_validate(response)
        raise NotImplementedError(
            "Wire this up to the real Gemini function-call response shape in production."
        )

    @staticmethod
    def _parse_voice_response(response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            return response
        raise NotImplementedError(
            "Wire this up to the real Gemini structured (VoiceIntentResponse) output."
        )


def _resolution_for_quality(quality: MatchQuality) -> str:
    return {
        MatchQuality.EXACT: "exact_match",
        MatchQuality.NEAR: "near_match",
        MatchQuality.MISS: "no_match",
    }[quality]
