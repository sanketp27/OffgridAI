"""tests/unit/test_discovery.py — OG-014 match-quality thresholds, OG-048 refinement."""

from __future__ import annotations

from agents.discovery import classify_match_quality
from agents.discovery_refinement import classify_refinement, infer_new_budget
from models.common import MatchQuality


class TestClassifyMatchQuality:
    def test_above_exact_threshold_is_exact(self) -> None:
        assert classify_match_quality(0.9, exact_threshold=0.75, near_threshold=0.4) == MatchQuality.EXACT

    def test_at_exact_threshold_is_exact(self) -> None:
        assert classify_match_quality(0.75, exact_threshold=0.75, near_threshold=0.4) == MatchQuality.EXACT

    def test_between_thresholds_is_near(self) -> None:
        assert classify_match_quality(0.6, exact_threshold=0.75, near_threshold=0.4) == MatchQuality.NEAR

    def test_at_near_threshold_is_near(self) -> None:
        assert classify_match_quality(0.4, exact_threshold=0.75, near_threshold=0.4) == MatchQuality.NEAR

    def test_below_near_threshold_is_miss(self) -> None:
        assert classify_match_quality(0.1, exact_threshold=0.75, near_threshold=0.4) == MatchQuality.MISS

    def test_zero_score_is_miss(self) -> None:
        assert classify_match_quality(0.0, exact_threshold=0.75, near_threshold=0.4) == MatchQuality.MISS


class TestClassifyRefinement:
    def test_price_down_keywords(self) -> None:
        assert classify_refinement("do you have anything cheaper?") == "price_down"
        assert classify_refinement("something more affordable") == "price_down"

    def test_price_up_keywords(self) -> None:
        assert classify_refinement("show me something more premium") == "price_up"

    def test_style_change_keywords(self) -> None:
        assert classify_refinement("I want something more minimal") == "style_change"

    def test_no_keyword_match_defaults_to_new_search(self) -> None:
        assert classify_refinement("actually forget it, show me umbrellas") == "new_search"

    def test_explicit_budget_extraction(self) -> None:
        assert infer_new_budget("something under 2500", current_budget=5000) == 2500.0

    def test_implicit_budget_reduction_without_explicit_number(self) -> None:
        # No explicit number in the utterance -> conservative 30% reduction.
        assert infer_new_budget("cheaper please", current_budget=1000) == 700.0

    def test_no_current_budget_and_no_explicit_number_returns_none(self) -> None:
        assert infer_new_budget("cheaper please", current_budget=None) is None
