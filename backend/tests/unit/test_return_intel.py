"""tests/unit/test_return_intel.py — OG-037 risk scoring, OG-038 disposition table."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agents.return_intel import compute_return_risk, get_disposition
from config import Settings
from models.return_assessment import Order


class TestComputeReturnRisk:
    def test_no_history_is_low_risk(self, settings: Settings) -> None:
        result = compute_return_risk([], current_sku_id="sku-1", settings=settings)
        assert result.tier == "low"
        assert result.score == 0
        assert result.factors == []

    def test_bracketing_detected(self, settings: Settings) -> None:
        history = [
            Order(order_id="o1", sku_id="sku-1", variant_id="M"),
            Order(order_id="o2", sku_id="sku-1", variant_id="L"),
        ]
        result = compute_return_risk(history, current_sku_id="sku-1", settings=settings)
        assert "bracketing" in result.factors
        assert result.score >= 30

    def test_rapid_return_detected(self, settings: Settings) -> None:
        delivered = datetime.now(UTC) - timedelta(hours=10)
        returned = delivered + timedelta(hours=2)  # well within the 48h window
        history = [
            Order(
                order_id="o1",
                sku_id="sku-1",
                delivered_at=delivered,
                returned_at=returned,
                was_returned=True,
            )
        ]
        result = compute_return_risk(history, current_sku_id="sku-1", settings=settings)
        assert "rapid_return" in result.factors

    def test_slow_return_not_flagged_as_rapid(self, settings: Settings) -> None:
        delivered = datetime.now(UTC) - timedelta(days=10)
        returned = delivered + timedelta(hours=settings.RAPID_RETURN_WINDOW_HOURS + 1)
        history = [
            Order(
                order_id="o1",
                sku_id="sku-1",
                delivered_at=delivered,
                returned_at=returned,
                was_returned=True,
            )
        ]
        result = compute_return_risk(history, current_sku_id="sku-1", settings=settings)
        assert "rapid_return" not in result.factors

    def test_prior_history_above_threshold(self, settings: Settings) -> None:
        history = [
            Order(order_id=f"o{i}", sku_id="sku-2", was_returned=True)
            for i in range(settings.PRIOR_RETURNS_THRESHOLD + 1)
        ]
        result = compute_return_risk(history, current_sku_id="sku-1", settings=settings)
        assert "prior_history" in result.factors

    def test_all_signals_combine_to_high_tier(self, settings: Settings) -> None:
        delivered = datetime.now(UTC) - timedelta(hours=5)
        returned = delivered + timedelta(hours=1)
        history = [
            Order(order_id="o1", sku_id="sku-1", variant_id="M"),
            Order(
                order_id="o2",
                sku_id="sku-1",
                variant_id="L",
                delivered_at=delivered,
                returned_at=returned,
                was_returned=True,
            ),
            *[Order(order_id=f"prior{i}", sku_id="other", was_returned=True) for i in range(3)],
        ]
        result = compute_return_risk(history, current_sku_id="sku-1", settings=settings)
        # bracketing(30) + rapid_return(25) + prior_history(20) = 75 -> high
        assert result.score == 75
        assert result.tier == "high"


class TestDispositionTable:
    def test_new_low_risk_is_restock(self) -> None:
        assert get_disposition("new", "low") == "restock"

    def test_new_high_risk_holds_for_review(self) -> None:
        assert get_disposition("new", "high") == "hold_for_review"

    def test_damaged_always_liquidate_regardless_of_risk(self) -> None:
        assert get_disposition("damaged", "low") == "liquidate"
        assert get_disposition("damaged", "medium") == "liquidate"
        assert get_disposition("damaged", "high") == "liquidate"

    def test_lightly_used_medium_risk_is_refurbish(self) -> None:
        assert get_disposition("lightly_used", "medium") == "refurbish"

    def test_unknown_combination_defaults_to_hold_for_review(self) -> None:
        assert get_disposition("unknown_condition", "low") == "hold_for_review"
