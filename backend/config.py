"""
config.py — Pydantic Settings for the OffGrid AI backend.

Load order (per Implementation Plan §12 Environment Strategy):
    1. Environment variables      (Cloud Run injects these in staging/production)
    2. `.env` file                (local dev only — gitignored)
    3. Secret Manager             (production secrets only — pulled lazily via `_get_secret`)

All "magic numbers" referenced throughout the agent mesh (score thresholds, CVR
constants, return-prone thresholds, crawl limits, etc.) live here so they are
documented in exactly one place and are trivially tunable per environment.

This is the single merge point between the backend's business-logic constants
(`VECTOR_MATCH_THRESHOLD_EXACT`, `INDUSTRY_CVR`, ...) and the common/core
infrastructure layer's settings (retry tuning, logging format, model auth
mode). Every `services/*` client and every agent takes its configuration
through this module — nothing outside it should hardcode a collection name,
model name, connection string, or business threshold.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, computed_field
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
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Environment / GCP wiring
    # ------------------------------------------------------------------ #
    env: str = "local"  # "local" | "staging" | "production"
    service_name: str = "offgrid-api"
    gcp_project_id: str = Field(default="offgrid-local-dev")
    firestore_database: str = "(default)"
    vertex_ai_location: str = "us-central1"
    gcs_bucket: str = "offgrid-ai-assets"
    bq_dataset: str = "offgrid_events"
    bq_events_table: str = "events"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def bq_events_table_fqn(self) -> str:
        """Fully-qualified `project.dataset.table` for the events mirror."""
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_events_table}"

    # Stored as a raw comma-separated string (CORS_ORIGINS=a,b,c in .env) —
    # deliberately *not* typed as `list[str]` directly: pydantic-settings
    # attempts to JSON-decode env values for list-typed fields before any
    # field validator runs, which rejects a plain comma-separated string
    # outright (raises at settings-construction time, not gracefully). The
    # `cors_origins` computed property below is the parsed `list[str]`
    # every caller should actually use.
    cors_origins_csv: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_csv.split(",") if origin.strip()]

    # Optional — only needed to generate V4 signed URLs when running under
    # Application Default Credentials that have no private key (e.g. the
    # Cloud Run metadata service account). See `services/storage.py`.
    gcp_service_account_email: str | None = None

    # ------------------------------------------------------------------ #
    # Firebase Auth
    # ------------------------------------------------------------------ #
    firebase_project_id: str | None = None
    # Path to a local service-account JSON for `local`/`staging` dev; in
    # `production`, firebase-admin picks up Application Default Credentials
    # on Cloud Run, so this is typically unset there.
    firebase_credentials_path: str | None = None

    # ------------------------------------------------------------------ #
    # Vertex AI / Gemini model identifiers + auth mode
    # ------------------------------------------------------------------ #
    # True  (default, production): call Gemini via Vertex AI — ADC / the
    #       Cloud Run service account, billed to gcp_project_id.
    # False: call Gemini via the public Gemini Developer API using
    #       `gemini_api_key` — handy for local dev without full GCP
    #       credentials configured.
    use_vertex_ai: bool = True
    gemini_api_key: str | None = None

    gemini_flash_model: str = "gemini-3.6-flash"
    gemini_pro_model: str = "gemini-3.6-pro"
    gemini_embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int = 768  # must match the Firestore vector index dimension

    gemini_default_temperature: float = 0.2
    gemini_default_max_output_tokens: int = 2048

    # ------------------------------------------------------------------ #
    # Firestore collection names — centralized here (not hardcoded in
    # services/firestore.py) so a rename, or per-environment namespacing
    # (e.g. a "_staging" suffix), is a config change, not a code change.
    # ------------------------------------------------------------------ #
    firestore_collection_sessions: str = "sessions"
    firestore_collection_catalog: str = "catalog"
    firestore_collection_events: str = "events"
    firestore_collection_insights: str = "insights"
    firestore_collection_return_assessments: str = "return_assessments"
    firestore_collection_follow_up_notifications: str = "follow_up_notifications"
    firestore_collection_merchant_chat_sessions: str = "merchant_chat_sessions"
    firestore_collection_catalog_import_jobs: str = "catalog_import_jobs"

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
    # Retry / backoff — shared by every outbound GCP call (core/retry.py)
    # ------------------------------------------------------------------ #
    retry_max_attempts: int = 5
    retry_initial_wait_seconds: float = 1.0
    retry_max_wait_seconds: float = 20.0
    retry_jitter_seconds: float = 1.0

    # ------------------------------------------------------------------ #
    # Logging (core/logging.py)
    # ------------------------------------------------------------------ #
    log_level: str = "INFO"
    # true => structured JSON (Cloud Logging compatible, used in staging/production).
    # false => pretty console renderer (local dev).
    log_json: bool = Field(default=False)

    # ------------------------------------------------------------------ #
    # Misc
    # ------------------------------------------------------------------ #
    request_timeout_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton (cached after first call)."""
    return Settings()
