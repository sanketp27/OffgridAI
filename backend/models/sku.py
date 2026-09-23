"""models/sku.py — `catalog` collection (Implementation Plan §6.1).

One document per SKU. `embedding` is indexed as a Firestore vector field
(cosine distance, dimension=768 — see `config.Settings.embedding_dimensions`).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from models.common import FirestoreModel, utcnow


class SKU(FirestoreModel):
    sku_id: str
    name: str
    description: str = ""
    category: str  # "footwear" | "apparel" | "home_goods" | "electronics" | ...
    subcategory: str | None = None
    price: float
    currency: str = "INR"
    stock: int = 0
    return_rate: float = 0.0  # 0.0-1.0; drives Fit-Check trigger (OG-019)
    image_url: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    embedding: list[float] = Field(default_factory=list)
    store_availability: dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("price")
    @classmethod
    def _price_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("price must be positive")
        return v

    @property
    def is_return_prone(self) -> bool:
        """Derived field — never stored redundantly, always computed from source fields.

        `category in RETURN_PRONE_CATEGORIES and return_rate > FIT_CHECK_RETURN_RATE_THRESHOLD`
        See `config.Settings.RETURN_PRONE_CATEGORIES` / `FIT_CHECK_RETURN_RATE_THRESHOLD`.
        """
        from config import get_settings

        settings = get_settings()
        return (
            self.category in settings.RETURN_PRONE_CATEGORIES
            and self.return_rate > settings.FIT_CHECK_RETURN_RATE_THRESHOLD
        )

    def stock_at(self, store_id: str) -> int:
        """Stock for one store, falling back to the aggregate `stock` field."""
        return self.store_availability.get(store_id, self.stock)


class SKUSearchResult(FirestoreModel):
    """A scored SKU returned from `FirestoreService.vector_search_catalog`."""

    sku: SKU
    score: float  # cosine similarity, 0.0-1.0
