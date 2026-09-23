"""routers/search.py — Discovery-facing endpoints (Implementation Plan §7.2).

    POST /search           shopper text/image query                [OG-012..018]
    POST /search/refine    iterative refinement on an active search [OG-048]
    POST /search/voice     voice/multilingual search                [OG-049]
    GET  /session/{id}     read back a session (widget reconnect)
"""

from __future__ import annotations

import base64
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from agents.fit_check import FitCheckAgent
from agents.orchestrator import Orchestrator, OrchestratorEventType
from dependencies import CurrentUser, get_db, get_orchestrator
from models.common import MatchQuality
from models.sku import SKU
from services.firestore import FirestoreService

router = APIRouter(tags=["search"])


class SKUResult(BaseModel):
    sku_id: str
    name: str
    price: float
    currency: str
    image_url: str
    match_explanation: str
    score: float

    @classmethod
    def from_sku(cls, sku: SKU, score: float) -> SKUResult:
        return cls(
            sku_id=sku.sku_id,
            name=sku.name,
            price=sku.price,
            currency=sku.currency,
            image_url=sku.image_url,
            match_explanation=sku.attributes.get("_match_explanation", ""),
            score=round(score, 4),
        )


class FitCheckPrompt(BaseModel):
    triggered: bool
    sku_id: str | None = None
    question: str | None = None


class SearchRequest(BaseModel):
    session_id: str | None = None
    store_id: str
    platform: str = "web_widget"
    query_text: str | None = None
    image_base64: str | None = None
    category_filter: str | None = None


class SearchResponse(BaseModel):
    session_id: str
    match_quality: MatchQuality
    results: list[SKUResult]
    fit_check: FitCheckPrompt


class RefineRequest(BaseModel):
    session_id: str
    refinement_text: str


class RefineResponse(BaseModel):
    session_id: str
    refinement_applied: str
    is_new_search: bool
    results: list[SKUResult]
    fit_check: FitCheckPrompt


class VoiceSearchRequest(BaseModel):
    session_id: str | None = None
    store_id: str
    platform: str = "mobile"
    audio_base64: str
    language_hint: str | None = None


class VoiceSearchResponse(BaseModel):
    session_id: str
    detected_language: str | None
    transcription: str | None
    match_quality: MatchQuality
    results: list[SKUResult]
    fit_check: FitCheckPrompt


async def _build_fit_check_prompt(
    orchestrator: Orchestrator,
    db: FirestoreService,
    *,
    store_id: str,
    claims: dict[str, Any],
    triggered: bool,
    sku_id: str | None,
) -> FitCheckPrompt:
    """Shared across /search, /search/refine, /search/voice: when the
    Discovery agent flags the top result as return-prone, generate the
    Fit-Check Agent's clarifying question inline so the widget can show it
    in the same response instead of a second round trip.
    """
    if not triggered or not sku_id:
        return FitCheckPrompt(triggered=False)
    sku = await db.get_sku(sku_id)
    if sku is None:
        return FitCheckPrompt(triggered=False)
    context = orchestrator.build_context(store_id=store_id, claims=claims)
    question = await FitCheckAgent(context).generate_question(sku)
    return FitCheckPrompt(triggered=True, sku_id=sku.sku_id, question=question)


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    claims: CurrentUser,
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
    db: Annotated[FirestoreService, Depends(get_db)],
) -> SearchResponse:
    session = await orchestrator.get_or_create_session(
        firestore=db,
        session_id=body.session_id,
        store_id=body.store_id,
        platform=body.platform,
        user_id=claims.get("uid"),
    )
    image_bytes = base64.b64decode(body.image_base64) if body.image_base64 else None

    outcome = await orchestrator.dispatch(
        OrchestratorEventType.SEARCH,
        store_id=body.store_id,
        claims=claims,
        session=session,
        query_text=body.query_text,
        image_bytes=image_bytes,
        category_filter=body.category_filter,
    )

    fit_check = await _build_fit_check_prompt(
        orchestrator,
        db,
        store_id=body.store_id,
        claims=claims,
        triggered=outcome.fit_check_triggered,
        sku_id=outcome.fit_check_sku_id,
    )

    return SearchResponse(
        session_id=outcome.session.session_id,
        match_quality=outcome.match_quality,
        results=[SKUResult.from_sku(r.sku, r.score) for r in outcome.results],
        fit_check=fit_check,
    )


@router.post("/search/refine", response_model=RefineResponse)
async def refine_search(
    body: RefineRequest,
    claims: CurrentUser,
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
    db: Annotated[FirestoreService, Depends(get_db)],
) -> RefineResponse:
    session = await db.get_session(body.session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    outcome = await orchestrator.dispatch(
        OrchestratorEventType.SEARCH_REFINE,
        store_id=session.store_id,
        claims=claims,
        session=session,
        refinement_text=body.refinement_text,
        # The MVP widget doesn't cache prior result SKU ids server-side
        # between turns, so this is an empty audit-trail placeholder --
        # extend `SearchRequest`/session storage to thread it through if
        # the "prior_result_sku_ids" field on search_refined events needs
        # to be populated for real.
        prior_result_sku_ids=[],
    )

    fit_check = await _build_fit_check_prompt(
        orchestrator,
        db,
        store_id=session.store_id,
        claims=claims,
        triggered=outcome.fit_check_triggered,
        sku_id=outcome.fit_check_sku_id,
    )

    return RefineResponse(
        session_id=outcome.session.session_id,
        refinement_applied=outcome.refinement_applied,
        is_new_search=outcome.is_new_search,
        results=[SKUResult.from_sku(r.sku, r.score) for r in outcome.results],
        fit_check=fit_check,
    )


@router.post("/search/voice", response_model=VoiceSearchResponse)
async def voice_search(
    body: VoiceSearchRequest,
    claims: CurrentUser,
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
    db: Annotated[FirestoreService, Depends(get_db)],
) -> VoiceSearchResponse:
    session = await orchestrator.get_or_create_session(
        firestore=db,
        session_id=body.session_id,
        store_id=body.store_id,
        platform=body.platform,
        user_id=claims.get("uid"),
    )
    audio_bytes = base64.b64decode(body.audio_base64)

    outcome = await orchestrator.dispatch(
        OrchestratorEventType.VOICE_SEARCH,
        store_id=body.store_id,
        claims=claims,
        session=session,
        audio_bytes=audio_bytes,
        language_hint=body.language_hint,
    )

    fit_check = await _build_fit_check_prompt(
        orchestrator,
        db,
        store_id=body.store_id,
        claims=claims,
        triggered=outcome.fit_check_triggered,
        sku_id=outcome.fit_check_sku_id,
    )

    return VoiceSearchResponse(
        session_id=outcome.session.session_id,
        detected_language=outcome.detected_language,
        transcription=outcome.transcription,
        match_quality=outcome.match_quality,
        results=[SKUResult.from_sku(r.sku, r.score) for r in outcome.results],
        fit_check=fit_check,
    )


@router.get("/session/{session_id}")
async def get_session(
    session_id: str, claims: CurrentUser, db: Annotated[FirestoreService, Depends(get_db)]
) -> dict[str, Any]:
    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session.model_dump(mode="json")
