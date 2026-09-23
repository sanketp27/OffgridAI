"""config.py — Centralized runtime configuration for the OffGrid AI backend.

This module is the **single source of truth** for every value that would
otherwise be hardcoded or scattered across the codebase:

  * GCP project / region wiring
  * Firestore database + collection names
  * BigQuery dataset / table names
  * Cloud Storage bucket + object-prefix layout
  * Gemini model identifiers (interactive chat, batch chat, embeddings)
  * Vector-search tuning constants (match thresholds, dimensionality)
  * Business scoring constants (documented, never re-derived downstream)
  * Retry / backoff tuning shared by every outbound GCP call

Precedence (highest wins), matching the "Environment Strategy" section of
the backend implementation plan:

  1. Real process environment variables (what Cloud Run injects)
  2. A local ``.env`` file (gitignored, local dev only — see ``.env.example``)
  3. The field defaults declared below

Nothing outside this module should call ``os.environ`` directly, and
nothing outside this module should hardcode a Firestore collection name, a
Gemini model string, a BigQuery table name, or a connection string. Every
client in ``services/`` takes a ``Settings`` instance (defaulting to
``get_settings()``) instead of importing constants itself.

In ``production``, secrets (service-account keys, third-party API keys)
should come from Secret Manager rather than ``.env`` — see
``load_secret()`` at the bottom of this module for the opt-in helper.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "staging", "production"]


class Settings(BaseSettings):
    """Application-wide settings, populated from env vars / ``.env``.

    Instantiate exactly once via :func:`get_settings` (cached). Every
    ``services/*`` client and every router/agent should receive its
    configuration through this object rather than reading environment
    variables itself.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Environment / service identity
    # ------------------------------------------------------------------
    env: Environment = Field(default="local", description='"local" | "staging" | "production"')
    service_name: str = Field(default="offgrid-api", description="Used as the logger name / Cloud Logging label")

    # ------------------------------------------------------------------
    # GCP project wiring
    # ------------------------------------------------------------------
    gcp_project_id: str = Field(default="offgrid-ai-hackathon", description="GCP project ID (also used as Vertex AI project)")
    vertex_ai_location: str = Field(default="us-central1", description="Region for Vertex AI / Gemini calls")

    # Toggle between calling Gemini through Vertex AI (service-account /
    # ADC auth, billed to gcp_project_id) and calling it through the
    # public Gemini Developer API (API-key auth). Vertex AI is the
    # non-negotiable production path per the backend plan; the API-key
    # path exists purely so a contributor can run services locally
    # without full GCP credentials configured.
    use_vertex_ai: bool = Field(default=True, description="True => Vertex AI (ADC/service account). False => Gemini Developer API (API key).")
    gemini_api_key: str | None = Field(default=None, description="Only used when use_vertex_ai=False")

    # ------------------------------------------------------------------
    # Firestore
    # ------------------------------------------------------------------
    firestore_database: str = Field(default="(default)", description="Firestore database ID")

    firestore_collection_sessions: str = Field(default="sessions")
    firestore_collection_catalog: str = Field(default="catalog")
    firestore_collection_events: str = Field(default="events")
    firestore_collection_insights: str = Field(default="insights")
    firestore_collection_return_assessments: str = Field(default="return_assessments")
    firestore_collection_follow_up_notifications: str = Field(default="follow_up_notifications")
    firestore_collection_merchant_chat_sessions: str = Field(default="merchant_chat_sessions")
    firestore_collection_catalog_import_jobs: str = Field(default="catalog_import_jobs")

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------
    # "firestore" is the MVP backend (native Firestore vector index on the
    # `catalog.embedding` field). "vertex_ai_vector_search" is the
    # production-scale stretch backend (Vertex AI Matching Engine).
    vector_search_backend: Literal["firestore", "vertex_ai_vector_search"] = Field(default="firestore")
    vector_search_field: str = Field(default="embedding", description="Vector field name on the catalog document")
    vector_search_distance_measure: Literal["cosine", "euclidean", "dot_product"] = Field(default="cosine")

    # Vertex AI Vector Search (stretch) — only required when
    # vector_search_backend == "vertex_ai_vector_search"
    vertex_ai_vector_index_endpoint: str | None = Field(default=None)
    vertex_ai_vector_deployed_index_id: str | None = Field(default=None)

    vector_match_threshold_exact: float = Field(default=0.75, description="score >= this => confident match")
    vector_match_threshold_near: float = Field(default=0.40, description="score >= this (but < exact) => near-match fallback")

    # ------------------------------------------------------------------
    # Gemini models (chat + embeddings)
    # ------------------------------------------------------------------
    # Defaults below match the model IDs named throughout the ticket specs
    # / implementation plan. Vertex AI model availability changes over
    # time — always verify against the Vertex AI Model Garden for the
    # target project before deploying, and override here (never in code)
    # if a different model should be used.
    gemini_flash_model: str = Field(default="gemini-3.6-flash", description="Interactive agents: Intent, Discovery, Fit-Check, Return Intelligence")
    gemini_pro_model: str = Field(default="gemini-3.6-pro", description="Batch Insight Agent synthesis")
    gemini_embedding_model: str = Field(default="gemini-embedding-2", description="Catalog + query embeddings")

    # `catalog.embedding` is stored/indexed at 768 dimensions (see
    # architecture.md). Gemini embedding models default to a larger
    # native size, so callers must pass `output_dimensionality` — this
    # setting is the one place that number is defined.
    gemini_embedding_dimension: int = Field(default=768, description="Must match the Firestore vector index dimension")

    gemini_default_temperature: float = Field(default=0.2)
    gemini_default_max_output_tokens: int = Field(default=2048)

    # ------------------------------------------------------------------
    # Cloud Storage
    # ------------------------------------------------------------------
    gcs_bucket: str = Field(default="offgrid-ai-assets")

    # ------------------------------------------------------------------
    # BigQuery
    # ------------------------------------------------------------------
    bq_dataset: str = Field(default="offgrid_events")
    bq_events_table: str = Field(default="events")

    @computed_field  # type: ignore[misc]
    @property
    def bq_events_table_fqn(self) -> str:
        """Fully-qualified ``project.dataset.table`` for the events mirror."""
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_events_table}"

    # ------------------------------------------------------------------
    # CORS (API layer — kept here since it's env-driven, not app logic)
    # ------------------------------------------------------------------
    # Stored as a raw comma-separated string (CORS_ORIGINS=a,b,c in .env) —
    # deliberately *not* typed as `list[str]` directly, because
    # pydantic-settings attempts to JSON-decode env values for list-typed
    # fields before any field validator runs, which rejects a plain
    # comma-separated string outright. `cors_origins` below is the parsed
    # `list[str]` every caller should actually use.
    cors_origins_csv: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    @computed_field  # type: ignore[misc]
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_csv.split(",") if origin.strip()]

    # ------------------------------------------------------------------
    # Business scoring constants (documented, never magic numbers downstream)
    # ------------------------------------------------------------------
    industry_cvr: float = Field(default=0.04, description="4% e-commerce industry-average conversion rate")
    insight_min_shoppers: int = Field(default=3, description="Min unique shoppers per cluster to surface an insight")
    fit_check_return_rate_threshold: float = Field(default=0.20, description="return_rate above which Fit-Check triggers")

    # ------------------------------------------------------------------
    # Retry / backoff (shared defaults — see core/retry.py)
    # ------------------------------------------------------------------
    retry_max_attempts: int = Field(default=5)
    retry_initial_wait_seconds: float = Field(default=1.0)
    retry_max_wait_seconds: float = Field(default=20.0)
    retry_jitter_seconds: float = Field(default=1.0)

    embedding_batch_size: int = Field(default=100, description="SKUs per embed_batch call, per OG-007/catalog import")
    embedding_batch_sleep_seconds: float = Field(default=0.1, description="Pause between embedding batches to respect quota")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True, description="True => structured JSON (Cloud Logging compatible). False => pretty console (local dev).")

    # ------------------------------------------------------------------
    # Secrets (production only — resolved via Secret Manager, see load_secret())
    # ------------------------------------------------------------------
    firebase_credentials_json: str | None = Field(
        default=None,
        description="Firebase Admin SDK service-account JSON as a string. "
        "Populate directly in .env for local dev, or via Secret Manager in production.",
    )

    @property
    def firebase_credentials(self) -> dict | None:
        if not self.firebase_credentials_json:
            return None
        return json.loads(self.firebase_credentials_json)

    @field_validator("env", "vector_search_backend", mode="before")
    @classmethod
    def _lowercase(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower()
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` singleton.

    ``lru_cache`` guarantees ``.env`` / env vars are parsed exactly once
    per process. Tests that need different settings should call
    ``get_settings.cache_clear()`` after monkeypatching the environment,
    or construct ``Settings(**overrides)`` directly instead of going
    through this accessor.
    """
    return Settings()


def load_secret(secret_id: str, *, settings: Settings | None = None, version: str = "latest") -> str:
    """Fetch a secret payload from Secret Manager.

    Only meaningful in ``staging``/``production`` where secrets are not
    materialized into ``.env``. Kept as an explicit, opt-in call (rather
    than a field ``default_factory``) so importing this module never
    requires network access or GCP credentials — every ``services/*``
    client works fine against plain ``.env`` values for local dev.

    Example:
        >>> settings = get_settings()
        >>> firebase_key_json = load_secret("firebase-sa-key", settings=settings)
    """
    from google.cloud import secretmanager  # local import: avoid hard dependency for local dev

    settings = settings or get_settings()
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{settings.gcp_project_id}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")
