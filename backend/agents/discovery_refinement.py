"""agents/discovery_refinement.py — Discovery Agent, Refinement mode (§8.2, OG-048).

Not a separate Gemini-backed agent: refinement utterances are classified by
a pure Python keyword match (no LLM call) so the p95 latency for a
refinement turn stays well under the full search path (§8.2 anti-pattern
note: "Refinement never re-calls Gemini for intent extraction when a Python
pattern match is sufficient").
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from agents.base import Agent
from agents.discovery import classify_match_quality
from agents.fit_check import should_trigger
from models.common import MatchQuality
from models.event import Event, EventType, compute_revenue_at_risk
from models.session import Session, StructuredIntent
from models.sku import SKUSearchResult

REFINEMENT_SIGNALS: dict[str, list[str]] = {
    "price_down": ["cheaper", "lower price", "budget", "affordable", "under"],
    "price_up": ["higher quality", "premium", "splurge", "more expensive"],
    "style_change": ["bolder", "more minimal", "modern", "classic", "colourful", "colorful"],
    # "new_search" has no keyword list — it is the default when nothing else matches.
}

_UNDER_AMOUNT_RE = re.compile(r"under\s*\$?\u20b9?\s*([\d,]+)", re.IGNORECASE)


def classify_refinement(utterance: str) -> str:
    """Pure keyword classifier -- §7.3 `POST /search/refine`.

    Returns one of "price_down" | "price_up" | "style_change" | "new_search".
    A directionless follow-up with no keyword match falls back to
    "new_search" per the OG-048 edge-case rule.
    """
    text = utterance.lower()
    for signal, keywords in REFINEMENT_SIGNALS.items():
        if any(keyword in text for keyword in keywords):
            return signal
    return "new_search"


def infer_new_budget(utterance: str, current_budget: float | None) -> float | None:
    """Extract an explicit ceiling ("under 2500") if present; otherwise
    apply a conservative 30% reduction to the current budget as a
    reasonable interpretation of "cheaper" with no explicit number.
    """
    match = _UNDER_AMOUNT_RE.search(utterance)
    if match:
        return float(match.group(1).replace(",", ""))
    if current_budget:
        return round(current_budget * 0.7, 2)
    return None


def extract_style(utterance: str) -> str:
    """Best-effort style keyword extraction for the "style_change" signal."""
    text = utterance.lower()
    for keyword in REFINEMENT_SIGNALS["style_change"]:
        if keyword in text:
            return keyword
    return utterance.strip()


@dataclass
class RefinementOutcome:
    session: Session
    refinement_applied: str
    updated_intent: StructuredIntent
    results: list[SKUSearchResult]
    is_new_search: bool
    event: Event
    fit_check_triggered: bool
    fit_check_sku_id: str | None


class DiscoveryRefinementAgent(Agent):
    """The IntentDiscoveryAgent invoked with `refinement=True` -- §8.2.

    Kept as its own class per the repository layout in §10.1
    (`agents/discovery_refinement.py`), but deliberately thin: all catalog
    retrieval logic is delegated to `IntentDiscoveryAgent` for the
    `new_search` fallback path so there is exactly one vector-search code
    path in the codebase.
    """

    name = "discovery_refinement"

    async def run(  # type: ignore[override]
        self,
        *,
        session: Session,
        refinement_text: str,
        prior_result_sku_ids: list[str],
    ) -> RefinementOutcome:
        settings = self.ctx.settings
        prior_intent = session.latest_intent()

        if prior_intent is None:
            # No context to refine -- must be treated as a fresh search.
            signal = "new_search"
        else:
            signal = classify_refinement(refinement_text)

        if signal == "new_search":
            from agents.discovery import IntentDiscoveryAgent

            fresh = await IntentDiscoveryAgent(self.ctx).run(
                session=session, query_text=refinement_text
            )
            return RefinementOutcome(
                session=fresh.session,
                refinement_applied="new_search",
                updated_intent=fresh.intent,
                results=fresh.results,
                is_new_search=True,
                event=fresh.event,
                fit_check_triggered=fresh.fit_check_triggered,
                fit_check_sku_id=fresh.fit_check_sku_id,
            )

        assert prior_intent is not None
        updated_intent = prior_intent.model_copy(deep=True)
        if signal == "price_down":
            updated_intent.budget = infer_new_budget(refinement_text, prior_intent.budget)
        elif signal == "price_up":
            updated_intent.budget = None
        elif signal == "style_change":
            updated_intent.attributes["style"] = extract_style(refinement_text)

        session.intent_history.append(updated_intent)

        query_vector = await self.ctx.embeddings.embed_text(updated_intent.to_embedding_text())
        results = await self.ctx.firestore.vector_search_catalog(
            query_vector,
            category_filter=updated_intent.category,
            max_price=updated_intent.budget,
            top_k=settings.SEARCH_TOP_K,
        )

        top_score = results[0].score if results else 0.0
        match_quality = classify_match_quality(
            top_score,
            exact_threshold=settings.VECTOR_MATCH_THRESHOLD_EXACT,
            near_threshold=settings.VECTOR_MATCH_THRESHOLD_NEAR,
        )
        matched = match_quality == MatchQuality.EXACT

        event = Event(
            event_id=str(uuid.uuid4()),
            session_id=session.session_id,
            user_id=session.user_id,
            store_id=session.store_id,
            platform=session.platform,
            type=EventType.SEARCH_REFINED,
            sku_ids=[r.sku.sku_id for r in results],
            matched=matched,
            score=top_score,
            resolution="narrowed",
            revenue_at_risk=compute_revenue_at_risk(
                results[0].sku.price if results else 0.0, matched
            ),
            query_text=refinement_text,
        )
        event.model_extra["prior_result_sku_ids"] = prior_result_sku_ids  # type: ignore[union-attr]
        await self.ctx.firestore.log_event(event)
        await self.ctx.firestore.save_session(session)

        fit_check_triggered = False
        fit_check_sku_id: str | None = None
        if results and should_trigger(results[0].sku, settings=settings):
            fit_check_triggered = True
            fit_check_sku_id = results[0].sku.sku_id

        return RefinementOutcome(
            session=session,
            refinement_applied=signal,
            updated_intent=updated_intent,
            results=results,
            is_new_search=False,
            event=event,
            fit_check_triggered=fit_check_triggered,
            fit_check_sku_id=fit_check_sku_id,
        )
