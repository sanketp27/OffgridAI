"""routers/return_intel.py — Store Associate return-intake endpoints (§7.2).

    POST /return                   associate uploads a photo of a returned item
    POST /return/{id}/confirm      associate/merchant confirms (or overrides) the disposition
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from agents.orchestrator import Orchestrator, OrchestratorEventType
from dependencies import get_db, get_orchestrator, get_storage, require_role
from models.return_assessment import ReturnAssessment
from services.firestore import FirestoreService
from services.storage import StorageService

router = APIRouter(tags=["return_intel"])

VALID_DISPOSITIONS = ("restock", "refurbish", "liquidate", "hold_for_review")


class ReturnAssessmentResponse(BaseModel):
    assessment_id: str
    condition: str
    condition_justification: str
    return_risk_tier: str
    risk_factors: list[str]
    recommended_disposition: str

    @classmethod
    def from_assessment(cls, a: ReturnAssessment) -> ReturnAssessmentResponse:
        return cls(
            assessment_id=a.assessment_id,
            condition=a.condition,
            condition_justification=a.condition_justification,
            return_risk_tier=a.return_risk_tier,
            risk_factors=a.risk_factors,
            recommended_disposition=a.recommended_disposition,
        )


class ConfirmDispositionRequest(BaseModel):
    confirmed_disposition: str


@router.post("/return", response_model=ReturnAssessmentResponse)
async def submit_return(
    claims: Annotated[dict, Depends(require_role(["associate", "merchant"]))],
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
    storage: Annotated[StorageService, Depends(get_storage)],
    order_id: Annotated[str, Form()],
    sku_id: Annotated[str, Form()],
    store_id: Annotated[str, Form()],
    photo: Annotated[UploadFile, File()],
) -> ReturnAssessmentResponse:
    image_bytes = await photo.read()
    object_path = StorageService.return_photo_path(store_id, f"{order_id}-{sku_id}")
    gcs_uri = storage.upload_bytes(
        object_path, image_bytes, content_type=photo.content_type or "image/jpeg"
    )

    assessment = await orchestrator.dispatch(
        OrchestratorEventType.RETURN,
        store_id=store_id,
        claims=claims,
        order_id=order_id,
        sku_id=sku_id,
        associate_uid=claims.get("uid", "unknown"),
        image_gcs_path=gcs_uri,
        image_bytes=image_bytes,
    )
    return ReturnAssessmentResponse.from_assessment(assessment)


@router.post("/return/{assessment_id}/confirm", response_model=ReturnAssessmentResponse)
async def confirm_disposition(
    assessment_id: str,
    body: ConfirmDispositionRequest,
    claims: Annotated[dict, Depends(require_role(["associate", "merchant"]))],
    db: Annotated[FirestoreService, Depends(get_db)],
) -> ReturnAssessmentResponse:
    if body.confirmed_disposition not in VALID_DISPOSITIONS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"confirmed_disposition must be one of {VALID_DISPOSITIONS}",
        )

    assessment = await db.get_return_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Return assessment not found")

    await db.confirm_return_assessment(
        assessment_id, body.confirmed_disposition, claims.get("uid", "unknown")
    )
    assessment.disposition_confirmed = True
    assessment.confirmed_disposition = body.confirmed_disposition
    return ReturnAssessmentResponse.from_assessment(assessment)
