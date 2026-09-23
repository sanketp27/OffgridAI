"""agents/insight.py — Insight Agent, batch mode (§8.2, §9.2, OG-023..028, OG-052, OG-053).

All numeric scoring is Python -- zero LLM arithmetic (Risk Register §14:
"LLM invents a number in Insight brief" is mitigated entirely by keeping
every number in this module, never asking Gemini to compute one). Gemini
Pro is used for exactly two things: semantic clustering of query strings
(meaning only, no numbers) and prose brief generation (grounded strictly on
the already-computed fields).
"""

from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass
from typing import Any

from agents.base import Agent, AgentContext
from config import Settings
from models.common import SignalType
from models.event import Event
from models.insight import Insight

# --- Step 3: trend + urgency (pure functions, hand-verifiable) ----------- #


def compute_trend(current_occurrences: int, prior_occurrences: int) -> float | None:
    """Period-over-period percentage change. `None` when there's no prior
    window to compare against (first-run demo case — §7.2 edge case).
    """
    if prior_occurrences <= 0:
        return None
    return round(((current_occurrences - prior_occurrences) / prior_occurrences) * 100, 1)


def median_aov(events: list[Event], sku_prices: dict[str, float], *, default: float = 0.0) -> float:
    """Median price of the primary SKU referenced by each event in the
    cluster -- used as the "average order value" proxy for revenue-at-risk.
    """
    prices = [
        sku_prices[e.sku_ids[0]]
        for e in events
        if e.sku_ids and e.sku_ids[0] in sku_prices
    ]
    if not prices:
        return default
    return round(statistics.median(prices), 2)


def compute_urgency_days(window_days: int, trend_pct: float | None) -> int | None:
    """OG-053 restock-by-date estimate, code-computed only.

    Derivation: at the trend-adjusted pace, a full window's worth of missed
    searches (`occurrences`) re-accumulates in
    `window_days / (1 + trend_pct/100)` days. (The `occurrences` term
    cancels algebraically -- see docstring math below -- so the formula
    only needs `window_days` and `trend_pct`.)

        projected_daily_rate = (occurrences / window_days) * (1 + trend_pct/100)
        urgency_days = occurrences / projected_daily_rate
                     = window_days / (1 + trend_pct/100)

    Example (matches §7.2's sample response): window_days=7, trend_pct=40.0
    -> 7 / 1.4 = 5.0 -> "restock within about 5 days".

    Returns `None` when there is insufficient history to trend (`trend_pct
    is None`) or when the trend implies vanishing demand (denominator <= 0)
    -- per the OG-053 edge case, omit rather than invent a number.
    """
    if trend_pct is None:
        return None
    denominator = 1 + (trend_pct / 100)
    if denominator <= 0:
        return None
    return max(1, round(window_days / denominator))


# --- Step 4: signal classification (OG-026, OG-052) ----------------------- #


@dataclass
class ClusterSignalInputs:
    """Everything `classify_signal` needs, gathered from OG-025 scoring +
    a catalog existence check. One instance per cluster.
    """

    is_fit_check_cluster: bool = False
    flip_rate: float | None = None  # fraction of fit_checks resolved "size_changed"
    sku_exists: bool = True  # does a matching SKU exist in the catalog at all?
    avg_match_score: float | None = None  # mean top vector-search score across the cluster
    avg_matched_price: float | None = None  # price of the SKU that matched, if any
    avg_budget: float | None = None  # mean shopper-stated budget across the cluster


def classify_signal(inputs: ClusterSignalInputs, *, settings: Settings) -> SignalType:
    """Rule-based classification -- §8.2 OG-026 / OG-052. NEVER an LLM judgment call.

    Documented tie-break precedence (OG-026 edge case: "a cluster that
    plausibly fits two categories"):

        1. SIZING_CONFUSION   — fit-check-flip clusters are a structurally
                                 different signal source (order-confirmation
                                 data, not search misses) and are checked
                                 first so they're never miscategorized as a
                                 search-side problem.
        2. STOCK_GAP          — checked before any match-score/price logic:
                                 if no SKU exists at all, there is nothing to
                                 be "priced too high" or "poorly tagged" --
                                 existence is checked before quality-of-match.
        3. PRICING_GAP (OG-052) — only reachable once a SKU is confirmed to
                                 exist AND the search worked well (high match
                                 score). A high score with price far above
                                 budget means Discovery did its job and the
                                 problem is price, not tagging or inventory.
        4. DISCOVERABILITY_GAP — the fallback: a SKU exists but didn't score
                                 well, so the likely fix is better tagging
                                 rather than sourcing new inventory.
    """
    if inputs.is_fit_check_cluster:
        threshold = 0.30  # >30% of fit-checks resolving "size_changed" signals real confusion
        if inputs.flip_rate is not None and inputs.flip_rate > threshold:
            return SignalType.SIZING_CONFUSION

    if not inputs.sku_exists:
        return SignalType.STOCK_GAP

    if (
        inputs.avg_match_score is not None
        and inputs.avg_match_score >= settings.VECTOR_MATCH_THRESHOLD_EXACT
        and inputs.avg_matched_price is not None
        and inputs.avg_budget is not None
        and inputs.avg_budget > 0
        and inputs.avg_matched_price > inputs.avg_budget * settings.PRICING_GAP_BUDGET_MARGIN
    ):
        return SignalType.PRICING_GAP

    return SignalType.DISCOVERABILITY_GAP


RECOMMENDED_ACTION_BY_SIGNAL: dict[SignalType, str] = {
    SignalType.STOCK_GAP: "Source a matching SKU for this demand cluster.",
    SignalType.DISCOVERABILITY_GAP: "Review tags/attributes on the closest-matching SKU(s).",
    SignalType.SIZING_CONFUSION: "Review the sizing/fit copy or chart for this SKU.",
    SignalType.PRICING_GAP: "Consider a promotion, bundle, or lower-priced alternative.",
}


# --- Cluster + brief data shapes ------------------------------------------ #


@dataclass
class ScoredCluster:
    label: str
    event_ids: list[str]
    occurrences: int
    unique_shoppers: int
    trend_pct: float | None
    est_revenue_at_risk: float
    signal_type: SignalType
    urgency_days: int | None = None
    brief: str = ""
    recommended_action: str = ""


BRIEF_PROMPT_TEMPLATE = """
Write 1-3 sentences in plain language for a retail merchant.
Use ONLY the numbers provided below. Do not compute, estimate, or invent any number.
State the trend only if trend_pct is not null.
End with one concrete action recommendation.

Data: {cluster_json}
""".strip()

CLUSTER_PROMPT_TEMPLATE = """
Group these {n} search queries by meaning into labeled clusters.
Return a JSON array: [{{"label": "...", "query_indices": [0,3,7]}}]
Do not compute counts, trends, or revenue. That is not your job here.
Queries: {queries_json}
""".strip()


class InsightAgent(Agent):
    name = "insight"

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.model = context.settings.gemini_pro_model

    async def run(
        self, *, time_window_days: int | None = None
    ) -> dict[str, Any]:
        """Full OG-023..028 pipeline — §9.2."""
        settings = self.ctx.settings
        store_id = self.ctx.store_id
        window_days = time_window_days or settings.INSIGHT_DEFAULT_WINDOW_DAYS

        # Step 1: aggregate raw events.
        events = await self.ctx.firestore.query_events(store_id, time_window_days=window_days)
        if len(events) < settings.INSIGHT_MIN_EVENTS:
            return {"insights": [], "reason": "insufficient_data", "event_count_processed": len(events)}

        prior_events = await self.ctx.firestore.query_events(
            store_id, time_window_days=window_days * 2
        )
        prior_events = [e for e in prior_events if e not in events]

        # Step 2: (would-be) Gemini Pro semantic clustering. Isolated behind
        # `_cluster_events` so numeric scoring below is independently testable.
        raw_clusters = await self._cluster_events(events)

        scored: list[ScoredCluster] = []
        for label, cluster_events in raw_clusters:
            occurrences = len(cluster_events)
            unique_shoppers = len({e.session_id for e in cluster_events})
            if unique_shoppers < settings.INSIGHT_MIN_SHOPPERS:
                continue  # Step 5 filtering

            prior_occurrences = sum(
                1
                for e in prior_events
                if e.query_text and label.lower() in (e.query_text or "").lower()
            )
            trend_pct = compute_trend(occurrences, prior_occurrences)

            sku_prices = await self._price_lookup(cluster_events)
            aov = median_aov(cluster_events, sku_prices)
            revenue_at_risk = round(occurrences * settings.INDUSTRY_CVR * aov, 2)

            signal_inputs = await self._build_signal_inputs(cluster_events, sku_prices)
            signal_type = classify_signal(signal_inputs, settings=settings)

            urgency_days = None
            if signal_type == SignalType.STOCK_GAP:
                urgency_days = compute_urgency_days(window_days, trend_pct)

            cluster = ScoredCluster(
                label=label,
                event_ids=[e.event_id for e in cluster_events],
                occurrences=occurrences,
                unique_shoppers=unique_shoppers,
                trend_pct=trend_pct,
                est_revenue_at_risk=revenue_at_risk,
                signal_type=signal_type,
                urgency_days=urgency_days,
                recommended_action=RECOMMENDED_ACTION_BY_SIGNAL[signal_type],
            )
            cluster.brief = await self._generate_brief(cluster)
            scored.append(cluster)

        insights: list[Insight] = []
        for cluster in scored:
            insight = Insight(
                insight_id=str(uuid.uuid4()),
                store_id=store_id,
                signal_type=cluster.signal_type,
                label=cluster.label,
                occurrences=cluster.occurrences,
                unique_shoppers=cluster.unique_shoppers,
                trend_pct=cluster.trend_pct,
                est_revenue_at_risk=cluster.est_revenue_at_risk,
                urgency_days=cluster.urgency_days,
                brief=cluster.brief,
                recommended_action=cluster.recommended_action,
                event_ids=cluster.event_ids,
            )
            await self.ctx.firestore.create_insight(insight)
            insights.append(insight)

        return {
            "insights": insights,
            "event_count_processed": len(events),
        }

    # ------------------------------------------------------------------ #
    # Integration seams (Gemini Pro calls) — isolated for testability
    # ------------------------------------------------------------------ #
    async def _cluster_events(self, events: list[Event]) -> list[tuple[str, list[Event]]]:
        """Step 2/3 — group events by semantic similarity of `query_text`.

        Production: a single Gemini Pro call with CLUSTER_PROMPT_TEMPLATE.
        Fallback here: group by exact `query_text` so the pipeline runs
        end-to-end offline; replace with the real clustering call for
        anything beyond identical repeated queries.
        """
        groups: dict[str, list[Event]] = {}
        for event in events:
            label = (event.query_text or event.sku_id or "unlabeled").strip().lower()
            groups.setdefault(label, []).append(event)
        return list(groups.items())

    async def _price_lookup(self, events: list[Event]) -> dict[str, float]:
        prices: dict[str, float] = {}
        seen: set[str] = set()
        for event in events:
            for sku_id in event.sku_ids:
                if sku_id in seen:
                    continue
                seen.add(sku_id)
                sku = await self.ctx.firestore.get_sku(sku_id)
                if sku:
                    prices[sku_id] = sku.price
        return prices

    async def _build_signal_inputs(
        self, events: list[Event], sku_prices: dict[str, float]
    ) -> ClusterSignalInputs:
        scores = [e.score for e in events if e.score is not None]
        avg_score = sum(scores) / len(scores) if scores else None

        matched_prices = [
            sku_prices[e.sku_ids[0]] for e in events if e.sku_ids and e.sku_ids[0] in sku_prices
        ]
        avg_price = sum(matched_prices) / len(matched_prices) if matched_prices else None

        # `budget` isn't stored on Event directly in this MVP schema; callers
        # with richer session history can extend this to pull the real
        # StructuredIntent.budget per event. Falls back to None (no pricing-
        # gap check possible) rather than guessing.
        avg_budget = None

        return ClusterSignalInputs(
            sku_exists=bool(sku_prices),
            avg_match_score=avg_score,
            avg_matched_price=avg_price,
            avg_budget=avg_budget,
        )

    async def _generate_brief(self, cluster: ScoredCluster) -> str:
        """Step 7 — grounded prose generation (OG-027).

        Deterministic template shown here (no invented numbers, exactly the
        computed fields) so the pipeline is runnable without live Vertex AI
        access; production replaces the body with a Gemini Pro call using
        BRIEF_PROMPT_TEMPLATE over `cluster.__dict__`.
        """
        trend_clause = f" (up {cluster.trend_pct:g}% vs last period)" if cluster.trend_pct else ""
        urgency_clause = (
            f" At the current pace, consider restocking within about {cluster.urgency_days} days."
            if cluster.urgency_days
            else ""
        )
        return (
            f"{cluster.occurrences} shoppers searched for \"{cluster.label}\"{trend_clause} "
            f"this period — an estimated ${cluster.est_revenue_at_risk:.2f} in revenue at risk. "
            f"{cluster.recommended_action}{urgency_clause}"
        )
