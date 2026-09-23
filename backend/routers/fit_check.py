"""routers/fit_check.py — Fit-Check + follow-up endpoints (§7.2).

    POST /fit-check                shopper's answer to a fit-check question
    GET  /follow-up/{session_id}   post-purchase follow-up message (OG-050)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agents.orchestrator import Orchestrator, OrchestratorEventType
from dependencies import CurrentUser, get_db, get_orchestrator
from services.firestore import FirestoreService

router = APIRouter(tags=["fit_check"])


class FitCheckRequest(BaseModel):
    session_id: str
    store_id: str
    platform: str = "web_widget"
    sku_id: str
    response_text: str | None = None  # None => shopper timed out (treated as "abandoned")
    original_variant: str | None = None
    new_variant: str | None = None


class FitCheckResponse(BaseModel):
    resolution: str
    cart_updated: bool
    follow_up_generated: bool


class FollowUpResponse(BaseModel):
    found: bool
    sku_id: str | None = None
    fit_check_resolution: str | None = None
    follow_up_message: str | None = None


@router.post("/fit-check", response_model=FitCheckResponse)
async def fit_check(
    body: FitCheckRequest,
    claims: CurrentUser,
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> FitCheckResponse:
    # NOTE: `store_id` is consumed by dispatch() itself to build the
    # AgentContext (FitCheckAgent reads it back via `self.ctx.store_id`),
    # so it is intentionally NOT repeated in the kwargs forwarded to
    # `FitCheckAgent.run()` below.
    outcome = await orchestrator.dispatch(
        OrchestratorEventType.FIT_CHECK_RESPONSE,
        store_id=body.store_id,
        claims=claims,
        session_id=body.session_id,
        platform=body.platform,
        user_id=claims.get("uid"),
        sku_id=body.sku_id,
        response_text=body.response_text,
        event_id_from_search=None,
        original_variant=body.original_variant,
        new_variant=body.new_variant,
    )
    return FitCheckResponse(
        resolution=outcome.resolution,
        cart_updated=outcome.cart_updated,
        follow_up_generated=outcome.follow_up is not None,
    )


@router.get("/follow-up/{session_id}", response_model=FollowUpResponse)
async def get_follow_up(
    session_id: str, claims: CurrentUser, db: Annotated[FirestoreService, Depends(get_db)]
) -> FollowUpResponse:
    notification = await db.get_follow_up_for_session(session_id)
    if notification is None:
        return FollowUpResponse(found=False)
    return FollowUpResponse(
        found=True,
        sku_id=notification.sku_id,
        fit_check_resolution=notification.fit_check_resolution,
        follow_up_message=notification.follow_up_message,
    )
