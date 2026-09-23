"""
config.py — Pydantic Settings for the OffGrid AI backend.

Load order (per Implementation Plan §12 Environment Strategy):
    1. Environment variables      (Cloud Run injects these in staging/production)
    2. `.env` file                (local dev only — gitignored)
    3. Secret Manager             (production secrets only — pulled lazily via `_get_secret`)

All "magic numbers" referenced throughout the agent mesh (score thresholds, CVR
constants, return-prone thresholds, crawl limits, etc.) live here so they are
documented in exactly one place and are trivially tunable per environment.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_secret(secret_id: str, project_id: str | None = None) -> str:
    """Fetch the latest version of a Secret Manager secret.

    Only called in `production` — see `Settings.model_post_init`. Kept as a
    module-level function (rather than inlined) so it can be monkeypatched
    in tests without touching real GCP credentials.
    """
    from google.cloud import secretmanager  # local import: avoid hard dep at import time

    client = secretmanager.SecretManagerServiceClient()
    project = project_id or _bootstrap_project_id()
    name = f"projects/{project}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def _bootstrap_project_id() -> str:
    """Resolve the GCP project id before full Settings are constructed."""
    import os

    return os.environ.get("GCP_PROJECT_ID", "")


class Settings(BaseSettings):
    """Application-wide configuration.

    Instantiate via `get_settings()` (cached) rather than constructing this
    class directly, so the whole app shares one Settings object.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Environment / GCP wiring
    # ------------------------------------------------------------------ #
    env: str = "local"  # "local" | "staging" | "production"
    gcp_project_id: str = Field(default="offgrid-local-dev")
    firestore_database: str = "(default)"
    vertex_ai_location: str = "us-central1"
    gcs_bucket: str = "offgrid-ai-assets"
    bq_dataset: str = "offgrid_events"
    bq_events_table: str = "events"

    cors_origins: list[str] = ["http://localhost:3000"]  # Next.js dev server

    # ------------------------------------------------------------------ #
    # Firebase Auth
    # ------------------------------------------------------------------ #
    firebase_project_id: str | None = None
    # Path to a local service-account JSON for `local`/`staging` dev; in
    # `production`, firebase-admin picks up Application Default Credentials
    # on Cloud Run, so this is typically unset there.
    firebase_credentials_path: str | None = None

    # ------------------------------------------------------------------ #
    # Vertex AI model identifiers
    # ------------------------------------------------------------------ #
    gemini_flash_model: str = "gemini-3.6-flash"
    gemini_pro_model: str = "gemini-3.6-pro"
    gemini_embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int = 768

    # ------------------------------------------------------------------ #
    # Discovery / vector-search thresholds (§7.2, §8.2, §9.1)
    # ------------------------------------------------------------------ #
    VECTOR_MATCH_THRESHOLD_EXACT: float = 0.75
    VECTOR_MATCH_THRESHOLD_NEAR: float = 0.40
    SEARCH_TOP_K: int = 5

    # ------------------------------------------------------------------ #
    # Fit-Check (§8.2 — OG-019)
    # ------------------------------------------------------------------ #
    FIT_CHECK_RETURN_RATE_THRESHOLD: float = 0.20
    RETURN_PRONE_CATEGORIES: tuple[str, ...] = ("footwear", "apparel", "electronics_accessories")

    # ------------------------------------------------------------------ #
    # Insight pipeline (§8.2, §9.2 — OG-023..028, OG-052, OG-053)
    # ------------------------------------------------------------------ #
    INDUSTRY_CVR: float = 0.04  # 4% e-commerce industry-average conversion rate
    INSIGHT_MIN_EVENTS: int = 5  # below this, skip clustering entirely
    INSIGHT_MIN_SHOPPERS: int = 3  # min unique shoppers per cluster to surface
    INSIGHT_DEFAULT_WINDOW_DAYS: int = 7
    PRICING_GAP_BUDGET_MARGIN: float = 1.15  # matched SKU >15% over stated budget => pricing gap

    # ------------------------------------------------------------------ #
    # Return Intelligence (§8.2 — OG-037/038/039)
    # ------------------------------------------------------------------ #
    RETURN_RISK_HIGH_THRESHOLD: int = 50
    RETURN_RISK_MEDIUM_THRESHOLD: int = 25
    RAPID_RETURN_WINDOW_HOURS: int = 48
    PRIOR_RETURNS_THRESHOLD: int = 2

    # ------------------------------------------------------------------ #
    # Catalog import pipeline (§8.2, §9.4 — Phase 5B)
    # ------------------------------------------------------------------ #
    CRAWL_MAX_DEPTH: int = 3
    CRAWL_RATE_LIMIT_SECONDS: float = 0.5
    MAX_PAGES_PER_JOB: int = 300
    EMBEDDING_BATCH_SIZE: int = 100
    EMBEDDING_BATCH_SLEEP_SECONDS: float = 0.1
    DEFAULT_RETURN_RATE_BY_CATEGORY: dict[str, float] = Field(
        default_factory=lambda: {
            "footwear": 0.22,
            "apparel": 0.18,
            "electronics": 0.12,
            "home_goods": 0.08,
            "accessories": 0.10,
            "other": 0.05,
        }
    )
    VALID_SKU_CATEGORIES: tuple[str, ...] = (
        "footwear",
        "apparel",
        "home_goods",
        "electronics",
        "accessories",
        "other",
    )
    VALID_CURRENCIES: tuple[str, ...] = ("INR", "USD", "GBP", "EUR")
    NON_PRODUCT_URL_PATTERNS: tuple[str, ...] = (
        "/about",
        "/contact",
        "/blog",
        "/faq",
        "/policy",
        "/privacy",
        "/terms",
        "/careers",
    )

    # ------------------------------------------------------------------ #
    # Misc
    # ------------------------------------------------------------------ #
    request_timeout_seconds: int = 30
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton (cached after first call)."""
    return Settings()
