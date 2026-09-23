"""tests/unit/test_catalog_import_normalization.py — Stage 3 validation/confidence/dedup."""

from __future__ import annotations

from agents.catalog_import import compute_confidence, deduplicate, slugify, validate_candidate
from models.catalog_import_job import SKUCandidate

VALID_CATEGORIES = ("footwear", "apparel", "home_goods", "electronics", "accessories", "other")


class TestValidateCandidate:
    def test_valid_candidate_passes(self) -> None:
        candidate = {"name": "Tote Bag", "category": "accessories", "price": 45.0, "currency": "USD"}
        is_valid, error = validate_candidate(candidate, valid_categories=VALID_CATEGORIES)
        assert is_valid is True
        assert error is None

    def test_missing_required_field(self) -> None:
        candidate = {"name": "Tote Bag", "category": "accessories", "currency": "USD"}
        is_valid, error = validate_candidate(candidate, valid_categories=VALID_CATEGORIES)
        assert is_valid is False
        assert error == "price_missing"

    def test_invalid_category(self) -> None:
        candidate = {
            "name": "Tote Bag", "category": "not_a_real_category", "price": 45.0, "currency": "USD",
        }
        is_valid, error = validate_candidate(candidate, valid_categories=VALID_CATEGORIES)
        assert is_valid is False
        assert error == "invalid_category"

    def test_zero_price_is_caught_as_missing(self) -> None:
        # 0 is falsy, so it's caught by the required-field presence check
        # before the price-specific `<= 0` check runs -- still correctly
        # rejected, just under the "_missing" error code rather than
        # "invalid_price".
        candidate = {"name": "Tote Bag", "category": "accessories", "price": 0, "currency": "USD"}
        is_valid, error = validate_candidate(candidate, valid_categories=VALID_CATEGORIES)
        assert is_valid is False
        assert error == "price_missing"

    def test_negative_price_invalid(self) -> None:
        candidate = {"name": "Tote Bag", "category": "accessories", "price": -5.0, "currency": "USD"}
        is_valid, error = validate_candidate(candidate, valid_categories=VALID_CATEGORIES)
        assert is_valid is False
        assert error == "invalid_price"

    def test_non_numeric_price_invalid(self) -> None:
        candidate = {
            "name": "Tote Bag", "category": "accessories", "price": "forty-five", "currency": "USD",
        }
        is_valid, error = validate_candidate(candidate, valid_categories=VALID_CATEGORIES)
        assert is_valid is False
        assert error == "invalid_price"

    def test_boolean_price_rejected(self) -> None:
        # bool is a subclass of int in Python -- explicitly guarded against.
        candidate = {"name": "Tote Bag", "category": "accessories", "price": True, "currency": "USD"}
        is_valid, error = validate_candidate(candidate, valid_categories=VALID_CATEGORIES)
        assert is_valid is False
        assert error == "invalid_price"


class TestComputeConfidence:
    def test_all_fields_present_scores_one(self) -> None:
        candidate = {
            "name": "Tote Bag", "price": 45.0, "category": "accessories",
            "image_url": "https://example.com/img.jpg", "description": "A canvas tote.",
        }
        assert compute_confidence(candidate) == 1.0

    def test_missing_optional_fields_reduces_score(self) -> None:
        candidate = {"name": "Tote Bag", "price": 45.0, "category": "accessories"}
        # 0.3 (name) + 0.25 (price) + 0.2 (category) = 0.75
        assert compute_confidence(candidate) == 0.75

    def test_no_fields_scores_zero(self) -> None:
        assert compute_confidence({}) == 0.0


class TestSlugify:
    def test_basic_slug(self) -> None:
        assert slugify("Heritage Canvas Tote") == "heritage-canvas-tote"

    def test_special_characters_collapsed(self) -> None:
        assert slugify("Men's Running Shoes (2024)") == "men-s-running-shoes-2024"

    def test_empty_name_gets_fallback_slug(self) -> None:
        assert slugify("").startswith("sku-")


class TestDeduplicate:
    def test_exact_case_insensitive_match_flagged_as_duplicate(self) -> None:
        candidates = [
            SKUCandidate(sku_id="a", name="Heritage Canvas Tote", category="accessories", price=45.0, currency="USD"),
            SKUCandidate(sku_id="b", name="New Item", category="accessories", price=20.0, currency="USD"),
        ]
        existing = {"heritage canvas tote"}
        result, skipped = deduplicate(candidates, existing)
        assert skipped == 1
        assert result[0].is_duplicate is True
        assert result[1].is_duplicate is False

    def test_no_matches_skips_none(self) -> None:
        candidates = [
            SKUCandidate(sku_id="a", name="Brand New Thing", category="accessories", price=45.0, currency="USD"),
        ]
        result, skipped = deduplicate(candidates, existing_names=set())
        assert skipped == 0
        assert result[0].is_duplicate is False
