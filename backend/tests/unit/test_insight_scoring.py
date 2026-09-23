"""tests/unit/test_insight_scoring.py — OG-024 trend, OG-053 urgency,
OG-026/OG-052 signal classification, revenue-at-risk inputs.

Two of the cases below (`test_urgency_matches_spec_example`,
`test_pricing_gap_hand_computed`) include the hand-computation in the
docstring/comments so the expected value is independently verifiable
without running the code.
"""

from __future__ import annotations

from agents.insight import (
    ClusterSignalInputs,
    classify_signal,
    compute_trend,
    compute_urgency_days,
    median_aov,
)
from config import Settings
from models.common import SignalType
from models.event import Event, EventType


class TestComputeTrend:
    def test_no_prior_history_returns_none(self) -> None:
        assert compute_trend(current_occurrences=10, prior_occurrences=0) is None

    def test_growth_percentage(self) -> None:
        # (14 - 10) / 10 * 100 = 40.0
        assert compute_trend(current_occurrences=14, prior_occurrences=10) == 40.0

    def test_decline_percentage(self) -> None:
        # (5 - 10) / 10 * 100 = -50.0
        assert compute_trend(current_occurrences=5, prior_occurrences=10) == -50.0


class TestComputeUrgencyDays:
    def test_urgency_matches_spec_example(self) -> None:
        """Hand computation (Implementation Plan §7.2 sample response):
        window_days=7, trend_pct=40.0
        urgency_days = window_days / (1 + trend_pct/100) = 7 / 1.4 = 5.0 -> 5
        """
        assert compute_urgency_days(window_days=7, trend_pct=40.0) == 5

    def test_no_trend_history_returns_none(self) -> None:
        assert compute_urgency_days(window_days=7, trend_pct=None) is None

    def test_flat_trend_returns_window_days(self) -> None:
        # 7 / (1 + 0/100) = 7.0 -> 7
        assert compute_urgency_days(window_days=7, trend_pct=0.0) == 7

    def test_collapsing_demand_returns_none(self) -> None:
        # trend_pct <= -100 makes the denominator <= 0 -- no meaningful estimate.
        assert compute_urgency_days(window_days=7, trend_pct=-150.0) is None

    def test_result_is_never_less_than_one_day(self) -> None:
        # Large positive trend would mathematically round to 0 -- floor at 1.
        assert compute_urgency_days(window_days=7, trend_pct=900.0) >= 1


class TestMedianAov:
    def test_median_of_matched_prices(self) -> None:
        events = [
            Event(
                event_id="e1", session_id="s1", store_id="st1", platform="web",
                type=EventType.SEARCH, sku_ids=["sku-a"],
            ),
            Event(
                event_id="e2", session_id="s2", store_id="st1", platform="web",
                type=EventType.SEARCH, sku_ids=["sku-b"],
            ),
            Event(
                event_id="e3", session_id="s3", store_id="st1", platform="web",
                type=EventType.SEARCH, sku_ids=["sku-c"],
            ),
        ]
        prices = {"sku-a": 10.0, "sku-b": 20.0, "sku-c": 30.0}
        assert median_aov(events, prices) == 20.0

    def test_no_priced_events_returns_default(self) -> None:
        events = [
            Event(
                event_id="e1", session_id="s1", store_id="st1", platform="web",
                type=EventType.SEARCH, sku_ids=[],
            )
        ]
        assert median_aov(events, {}, default=0.0) == 0.0


class TestClassifySignal:
    """Three hand-crafted clusters covering the OG-026 test matrix, plus the
    OG-052 pricing-gap addition and the fit-check-derived sizing signal.
    """

    def test_stock_gap_when_no_matching_sku_exists(self, settings: Settings) -> None:
        # "waterproof hiking boots" -- zero SKUs in the catalog match at all.
        inputs = ClusterSignalInputs(sku_exists=False)
        assert classify_signal(inputs, settings=settings) == SignalType.STOCK_GAP

    def test_discoverability_gap_when_sku_exists_but_scores_low(self, settings: Settings) -> None:
        # "sneakers" -- a SKU tagged "athletic shoes" exists but the vector
        # search scored it below the exact-match threshold.
        inputs = ClusterSignalInputs(
            sku_exists=True,
            avg_match_score=0.5,  # below settings.VECTOR_MATCH_THRESHOLD_EXACT (0.75)
            avg_matched_price=60.0,
            avg_budget=60.0,
        )
        assert classify_signal(inputs, settings=settings) == SignalType.DISCOVERABILITY_GAP

    def test_pricing_gap_hand_computed(self, settings: Settings) -> None:
        """OG-052: "yoga mat under $30", closest match scores 0.92 at $65.
        avg_budget * PRICING_GAP_BUDGET_MARGIN = 30 * 1.15 = 34.5
        65 > 34.5 and score (0.92) >= 0.75 -> PRICING_GAP.
        """
        inputs = ClusterSignalInputs(
            sku_exists=True, avg_match_score=0.92, avg_matched_price=65.0, avg_budget=30.0
        )
        assert classify_signal(inputs, settings=settings) == SignalType.PRICING_GAP

    def test_high_score_within_budget_falls_back_to_discoverability(
        self, settings: Settings
    ) -> None:
        # High match score AND price within budget -- shouldn't happen for a
        # true "no purchase" cluster, but the classifier must not silently
        # misclassify it as a pricing problem.
        inputs = ClusterSignalInputs(
            sku_exists=True, avg_match_score=0.9, avg_matched_price=25.0, avg_budget=30.0
        )
        assert classify_signal(inputs, settings=settings) == SignalType.DISCOVERABILITY_GAP

    def test_sizing_confusion_from_fit_check_flip_rate(self, settings: Settings) -> None:
        inputs = ClusterSignalInputs(is_fit_check_cluster=True, flip_rate=0.45)
        assert classify_signal(inputs, settings=settings) == SignalType.SIZING_CONFUSION

    def test_low_flip_rate_is_not_sizing_confusion(self, settings: Settings) -> None:
        # Low flip rate + SKU exists + no strong score/price signal -> falls
        # through to the discoverability default rather than sizing_confusion.
        inputs = ClusterSignalInputs(is_fit_check_cluster=True, flip_rate=0.1, sku_exists=True)
        assert classify_signal(inputs, settings=settings) == SignalType.DISCOVERABILITY_GAP

    def test_sizing_confusion_checked_before_stock_gap(self, settings: Settings) -> None:
        """Tie-break precedence: a fit-check cluster with a high flip rate
        is SIZING_CONFUSION even if `sku_exists=False` happens to be set --
        sizing signals are checked first because they come from a
        structurally different data source (order confirmations, not
        search misses).
        """
        inputs = ClusterSignalInputs(is_fit_check_cluster=True, flip_rate=0.5, sku_exists=False)
        assert classify_signal(inputs, settings=settings) == SignalType.SIZING_CONFUSION
