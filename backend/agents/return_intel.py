"""agents/return_intel.py — Return Intelligence Agent (§8.2, OG-037..039).

Two-stage design, per the architecture review fix -- these stages are
ALWAYS kept separate:

  Stage 1 (Gemini Vision): condition grading ONLY. The prompt explicitly
           forbids any fraud/behavior/authenticity claim.
  Stage 2 (Python, NO LLM): return-risk scoring from order history, and a
           fixed disposition lookup table. Numbers a merchant sees here
           must never come from the model.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from agents.base import Agent, AgentContext
from config import Settings
from models.return_assessment import Order, ReturnAssessment

CONDITION_PROMPT = """
Classify the physical condition of the returned item in this photo.
Output ONLY one of: new | lightly_used | damaged
Then provide ONE sentence citing visible evidence in the image.
Do NOT make any claim about fraud, return history, customer behavior, or authenticity.
""".strip()

# Disposition lookup -- Python dict, NOT the LLM. `"*"` matches any risk tier.
DISPOSITION_RULES: dict[tuple[str, str], str] = {
    ("new", "low"): "restock",
    ("new", "medium"): "restock",
    ("new", "high"): "hold_for_review",
    ("lightly_used", "low"): "refurbish",
    ("lightly_used", "medium"): "refurbish",
    ("lightly_used", "high"): "hold_for_review",
    ("damaged", "low"): "liquidate",
    ("damaged", "medium"): "liquidate",
    ("damaged", "high"): "liquidate",
}


def get_disposition(condition: str, risk_tier: str) -> str:
    """Deterministic disposition lookup -- falls back to `hold_for_review`
    for any condition/tier combination not explicitly enumerated, so an
    unexpected model output never silently produces a wrong action.
    """
    return DISPOSITION_RULES.get((condition, risk_tier), "hold_for_review")


@dataclass
class ReturnRiskResult:
    tier: str  # "low" | "medium" | "high"
    factors: list[str] = field(default_factory=list)
    score: int = 0


def compute_return_risk(
    order_history: list[Order],
    *,
    current_sku_id: str,
    settings: Settings,
    now: datetime | None = None,
) -> ReturnRiskResult:
    """Stage 2 risk scoring -- pure Python, §8.2.

    Signals:
      * bracketing        — multiple variants of the same SKU ordered together (+30)
      * rapid_return       — returned within RAPID_RETURN_WINDOW_HOURS of delivery (+25)
      * prior_history       — more than PRIOR_RETURNS_THRESHOLD past returns (+20)
    """
    now = now or datetime.now(UTC)
    score = 0
    factors: list[str] = []

    variants_ordered = {o.variant_id for o in order_history if o.sku_id == current_sku_id}
    variants_ordered.discard(None)
    if len({v for v in variants_ordered if v is not None}) > 1:
        score += 30
        factors.append("bracketing")

    current_order = next(
        (o for o in order_history if o.sku_id == current_sku_id and o.returned_at), None
    )
    if current_order and current_order.delivered_at and current_order.returned_at:
        held = current_order.returned_at - current_order.delivered_at
        if held < timedelta(hours=settings.RAPID_RETURN_WINDOW_HOURS):
            score += 25
            factors.append("rapid_return")

    past_returns = [o for o in order_history if o.was_returned]
    if len(past_returns) > settings.PRIOR_RETURNS_THRESHOLD:
        score += 20
        factors.append("prior_history")

    if score >= settings.RETURN_RISK_HIGH_THRESHOLD:
        tier = "high"
    elif score >= settings.RETURN_RISK_MEDIUM_THRESHOLD:
        tier = "medium"
    else:
        tier = "low"

    return ReturnRiskResult(tier=tier, factors=factors, score=score)


class ReturnIntelligenceAgent(Agent):
    name = "return_intel"

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.model = context.settings.gemini_flash_model

    async def grade_condition(self, image_bytes: bytes) -> tuple[str, str]:
        """Stage 1 -- Gemini Vision condition grading.

        Returns `(condition, justification)`. Production implementation
        calls `self.gemini.generate(..., contents=[image_bytes])` with
        CONDITION_PROMPT and parses the two-part output; stubbed here with
        a safe, conservative default so the pipeline is runnable end to end
        before Vertex AI vision access is wired up.
        """
        return "lightly_used", "Automated grading pending Vertex AI Vision integration."

    async def run(  # type: ignore[override]
        self,
        *,
        order_id: str,
        sku_id: str,
        associate_uid: str,
        image_gcs_path: str,
        image_bytes: bytes,
    ) -> ReturnAssessment:
        store_id = self.ctx.store_id
        condition, justification = await self.grade_condition(image_bytes)

        order_history_raw = await self.ctx.firestore.get_order_history(order_id, sku_id)
        order_history = [Order.model_validate(o) for o in order_history_raw]
        risk = compute_return_risk(
            order_history, current_sku_id=sku_id, settings=self.ctx.settings
        )

        disposition = get_disposition(condition, risk.tier)

        assessment = ReturnAssessment(
            assessment_id=str(uuid.uuid4()),
            order_id=order_id,
            sku_id=sku_id,
            store_id=store_id,
            associate_uid=associate_uid,
            image_gcs_path=image_gcs_path,
            condition=condition,
            condition_justification=justification,
            return_risk_tier=risk.tier,
            risk_factors=risk.factors,
            recommended_disposition=disposition,
            disposition_confirmed=False,
        )
        await self.ctx.firestore.create_return_assessment(assessment)
        return assessment
