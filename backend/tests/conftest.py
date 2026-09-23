"""tests/conftest.py — shared fixtures for the unit test suite.

Deliberately does not touch any real GCP service: every fixture here is a
plain in-memory model instance or a `Settings()` constructed from defaults
(no `.env` / Secret Manager access needed). Tests that need Firestore/Vertex
AI live under `tests/integration/` and are excluded by default (see
`pyproject.toml`'s `addopts = "-m 'not integration'"`).
"""

from __future__ import annotations

import pytest

from config import Settings
from models.sku import SKU


@pytest.fixture
def settings() -> Settings:
    return Settings(gcp_project_id="test-project")


@pytest.fixture
def return_prone_sneaker(settings: Settings) -> SKU:
    return SKU(
        sku_id="sneaker-001",
        name="Trail Runner Sneaker",
        category="footwear",
        price=89.99,
        return_rate=0.28,
        attributes={"fit": "true to size", "material": "mesh"},
    )


@pytest.fixture
def low_return_home_good(settings: Settings) -> SKU:
    return SKU(
        sku_id="mug-001",
        name="Ceramic Mug",
        category="home_goods",
        price=14.99,
        return_rate=0.03,
    )
