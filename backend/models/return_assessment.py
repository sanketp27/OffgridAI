"""models/return_assessment.py — `return_assessments` collection (§6.1)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from models.common import FirestoreModel, utcnow


class ReturnAssessment(FirestoreModel):
    assessment_id: str
    order_id: str
    sku_id: str
    store_id: str
    associate_uid: str
    image_gcs_path: str

    # --- Photo-derived (Gemini Vision, Stage 1 — NO fraud language permitted) ---
    condition: str = ""  # "new" | "lightly_used" | "damaged"
    condition_justification: str = ""

    # --- Order-history-derived (Python code only, Stage 2) ---
    return_risk_tier: str = ""  # "low" | "medium" | "high"
    risk_factors: list[str] = Field(default_factory=list)

    # --- Disposition (rule-based lookup table, NOT the LLM) ---
    recommended_disposition: str = ""  # "restock" | "refurbish" | "liquidate" | "hold_for_review"
    disposition_confirmed: bool = False
    confirmed_disposition: str | None = None
    confirmed_by_uid: str | None = None

    created_at: datetime = Field(default_factory=utcnow)
    confirmed_at: datetime | None = None


class Order(FirestoreModel):
    """Minimal order-history record used by `agents.return_intel.compute_return_risk`.

    Not a Firestore-native collection in this plan — populated from whatever
    order-history source the merchant integration provides (stubbed here so
    the risk-scoring function has a stable, testable input contract).
    """

    order_id: str
    sku_id: str
    variant_id: str | None = None
    delivered_at: datetime | None = None
    returned_at: datetime | None = None
    was_returned: bool = False
