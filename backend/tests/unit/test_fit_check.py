"""tests/unit/test_fit_check.py — OG-019 trigger condition, OG-021 response
classification, OG-050 follow-up eligibility.
"""

from __future__ import annotations

from agents.fit_check import classify_response, should_trigger
from config import Settings
from models.follow_up_notification import should_generate_follow_up
from models.sku import SKU


class TestShouldTrigger:
    def test_triggers_for_return_prone_category_above_threshold(
        self, return_prone_sneaker: SKU, settings: Settings
    ) -> None:
        assert should_trigger(return_prone_sneaker, settings=settings) is True

    def test_does_not_trigger_for_low_return_rate(self, settings: Settings) -> None:
        sku = SKU(sku_id="s1", name="Sneaker", category="footwear", price=50.0, return_rate=0.05)
        assert should_trigger(sku, settings=settings) is False

    def test_does_not_trigger_for_non_return_prone_category(
        self, low_return_home_good: SKU, settings: Settings
    ) -> None:
        # even if we hypothetically bump its return_rate, category gates first
        low_return_home_good.return_rate = 0.99
        assert should_trigger(low_return_home_good, settings=settings) is False

    def test_boundary_exact_threshold_does_not_trigger(self, settings: Settings) -> None:
        """`> threshold`, not `>=` -- exactly-at-threshold should NOT trigger."""
        sku = SKU(
            sku_id="s2",
            name="Boot",
            category="footwear",
            price=50.0,
            return_rate=settings.FIT_CHECK_RETURN_RATE_THRESHOLD,
        )
        assert should_trigger(sku, settings=settings) is False


class TestClassifyResponse:
    def test_timeout_is_abandoned(self) -> None:
        assert classify_response(None) == "abandoned"
        assert classify_response("") == "abandoned"
        assert classify_response("   ") == "abandoned"

    def test_size_change_phrases(self) -> None:
        assert classify_response("I'll go with a 9.5") == "size_changed"
        assert classify_response("Let me take the smaller one") == "size_changed"

    def test_variant_change_phrases(self) -> None:
        assert classify_response("Actually, a different color please") == "variant_changed"

    def test_confirmation_phrases(self) -> None:
        assert classify_response("Yes, that's fine") == "confirmed"
        assert classify_response("I'm good, keep it") == "confirmed"

    def test_unmatched_response_defaults_to_confirmed(self) -> None:
        # A real, engaged response that doesn't match a known pattern should
        # not be silently dropped as "abandoned".
        assert classify_response("sounds great, thanks!") == "confirmed"


class TestFollowUpEligibility:
    def test_confirmed_and_size_changed_are_eligible(self) -> None:
        assert should_generate_follow_up("confirmed") is True
        assert should_generate_follow_up("size_changed") is True

    def test_abandoned_and_variant_changed_are_not_eligible(self) -> None:
        assert should_generate_follow_up("abandoned") is False
        assert should_generate_follow_up("variant_changed") is False
