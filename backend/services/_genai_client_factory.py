"""services/_genai_client_factory.py — Shared `google-genai` Client construction.

Internal helper shared by `agents/base.py`'s `GeminiClient` (chat/generation)
and `services/embeddings.py`'s `EmbeddingsService` (embeddings) so both talk
to the same SDK client construction logic instead of duplicating the
Vertex-AI-vs-Developer-API branching.

IMPORTANT — SDK choice: as of this writing, `vertexai.generative_models`
and friends (the generative-AI modules that used to ship inside
`google-cloud-aiplatform`) are deprecated and being removed. The current,
supported way to call Gemini — on Vertex AI *or* the public Gemini
Developer API — is the unified `google-genai` SDK (`from google import
genai`), used here. Do not reintroduce the legacy `vertexai` generative
modules.
"""

from __future__ import annotations

from google import genai

from config import Settings, get_settings
from core.exceptions import ConfigurationError

# Keyed by `id(settings)` rather than `functools.lru_cache` directly on the
# function: `Settings` (a Pydantic BaseSettings) is not frozen/hashable by
# default, so an `lru_cache`-decorated function taking it as an argument
# would raise `TypeError: unhashable type` the moment a caller passed a
# `Settings` instance explicitly (e.g. in tests). `get_settings()` itself
# is an `lru_cache`d singleton, so `id(settings)` is stable across the
# default call path and this still only builds one client per process.
_client_cache: dict[int, genai.Client] = {}


def get_genai_client(settings: Settings | None = None) -> genai.Client:
    """Return a process-wide `genai.Client`, configured per `Settings`.

    `settings.use_vertex_ai` selects the auth/billing path:
      * True  (default, production): Vertex AI mode. Auth via Application
        Default Credentials / the Cloud Run service account. Billed to
        `settings.gcp_project_id` in `settings.vertex_ai_location`.
      * False: Gemini Developer API mode, authenticated with
        `settings.gemini_api_key`. Useful for local development without
        full GCP credentials configured.

    Cached because `genai.Client` manages its own HTTP connection pool and
    should not be re-created per call.
    """
    settings = settings or get_settings()
    cache_key = id(settings)
    if cache_key in _client_cache:
        return _client_cache[cache_key]

    if settings.use_vertex_ai:
        client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.vertex_ai_location,
        )
    else:
        if not settings.gemini_api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY is required when USE_VERTEX_AI=false",
                code="missing_gemini_api_key",
            )
        client = genai.Client(api_key=settings.gemini_api_key)

    _client_cache[cache_key] = client
    return client
