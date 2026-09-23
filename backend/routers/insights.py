"""routers/insights.py — Merchant Dashboard endpoints (§7.2).

    GET  /insights              list stored insights, ranked by revenue-at-risk
    POST /insights/generate     trigger the batch Insight Agent pipeline    [OG-023..028]
    POST /insights/chat         ask-your-data merchant chat                 [OG-051]
    GET  /events/aggregate      raw event counts (debugging / power users)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from agents.orchestrator import Orchestrator, OrchestratorEventType
from dependencies import (
    CurrentUser,
    get_bigquery,
    get_db,
    get_orchestrator,
    require_role,
    require_store_match,
)
from models.insight import Insight
from services.bigquery import BigQueryService
from services.firestore import FirestoreService

router = APIRouter(tags=["insights"])


class InsightResponse(BaseModel):
    insight_id: str
    signal_type: str
    label: str
    occurrences: int
    unique_shoppers: int
    trend_pct: float | None
    est_revenue_at_risk: float
    urgency_days: int | None
    brief: str
    recommended_action: str

    @classmethod
    def from_insight(cls, i: Insight) -> InsightResponse:
        return cls(
            insight_id=i.insight_id,
            signal_type=i.signal_type.value,
            label=i.label,
            occurrences=i.occurrences,
            unique_shoppers=i.unique_shoppers,
            trend_pct=i.trend_pct,
            est_revenue_at_risk=i.est_revenue_at_risk,
            urgency_days=i.urgency_days,
            brief=i.brief,
            recommended_action=i.recommended_action,
        )


class GenerateInsightsRequest(BaseModel):
    store_id: str
    time_window_days: int | None = None


class GenerateInsightsResponse(BaseModel):
    insights: list[InsightResponse]
    event_count_processed: int
    reason: str | None = None


class ChatRequest(BaseModel):
    store_id: str
    chat_session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    chat_session_id: str
    answer: str
    unanswerable: bool
    sources: list[dict]


@router.get("/insights", response_model=list[InsightResponse])
async def list_insights(
    claims: CurrentUser,
    db: Annotated[FirestoreService, Depends(get_db)],
    store_id: str = Query(...),
    top_n: int | None = Query(default=None, ge=1, le=50),
) -> list[InsightResponse]:
    require_store_match(claims, store_id)
    insights = await db.get_insights(store_id, top_n=top_n)
    return [InsightResponse.from_insight(i) for i in insights]


@router.post("/insights/generate", response_model=GenerateInsightsResponse)
async def generate_insights(
    body: GenerateInsightsRequest,
    claims: Annotated[dict, Depends(require_role(["merchant", "admin"]))],
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> GenerateInsightsResponse:
    require_store_match(claims, body.store_id)
    result = await orchestrator.dispatch(
        OrchestratorEventType.INSIGHTS_GENERATE,
        store_id=body.store_id,
        claims=claims,
        time_window_days=body.time_window_days,
    )
    return GenerateInsightsResponse(
        insights=[InsightResponse.from_insight(i) for i in result["insights"]],
        event_count_processed=result["event_count_processed"],
        reason=result.get("reason"),
    )


@router.post("/insights/chat", response_model=ChatResponse)
async def insights_chat(
    body: ChatRequest,
    claims: Annotated[dict, Depends(require_role(["merchant", "admin"]))],
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> ChatResponse:
    require_store_match(claims, body.store_id)
    outcome = await orchestrator.dispatch(
        OrchestratorEventType.INSIGHTS_CHAT,
        store_id=body.store_id,
        claims=claims,
        chat_session_id=body.chat_session_id,
        message=body.message,
    )
    return ChatResponse(
        chat_session_id=outcome.chat_session_id,
        answer=outcome.answer,
        unanswerable=outcome.unanswerable,
        sources=[s.model_dump(mode="json") for s in outcome.sources],
    )


@router.get("/events/aggregate")
async def events_aggregate(
    claims: Annotated[dict, Depends(require_role(["merchant", "admin"]))],
    bq: Annotated[BigQueryService, Depends(get_bigquery)],
    store_id: str = Query(...),
    event_type: str | None = Query(default=None),
    date_range_days: int = Query(default=7, ge=1, le=365),
) -> dict:
    require_store_match(claims, store_id)
    sql = f"""
        SELECT type, resolution, COUNT(*) AS count, SUM(revenue_at_risk) AS revenue_at_risk
        FROM `{bq.events_table_ref}`
        WHERE store_id = @store_id
          AND created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
          {"AND type = @event_type" if event_type else ""}
        GROUP BY type, resolution
        ORDER BY count DESC
    """
    params = {"store_id": store_id, "days": date_range_days}
    if event_type:
        params["event_type"] = event_type
    rows = bq.query(sql, params)
    return {"store_id": store_id, "date_range_days": date_range_days, "rows": rows}
