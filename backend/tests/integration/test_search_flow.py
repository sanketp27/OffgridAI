"""tests/integration/test_search_flow.py — end-to-end Discovery Agent flow.

Excluded from the default `pytest` run (see `pyproject.toml`'s
`-m 'not integration'`). Run explicitly with:

    pytest tests/integration -m integration

Requires either the Firestore emulator (`gcloud emulators firestore start`,
with `FIRESTORE_EMULATOR_HOST` set) or a real dev-project Firestore
instance, plus live Vertex AI credentials for the embedding + Gemini calls.
"""

from __future__ import annotations

import pytest

from agents.base import AgentContext
from agents.discovery import IntentDiscoveryAgent
from config import get_settings
from models.session import Session
from services.bigquery import BigQueryService
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService
from services.storage import StorageService


@pytest.mark.integration
async def test_search_against_seeded_catalog_returns_ranked_results() -> None:
    """Smoke test: seed a couple of SKUs, run a real search, assert the
    response shape and that Firestore persisted the resulting `Event`.

    Left intentionally unimplemented (`pytest.skip`) in the scaffold --
    fill in with real `FirestoreService`/`EmbeddingsService` calls once the
    emulator or a dev project is wired into CI.
    """
    pytest.skip("Wire up the Firestore emulator / dev project before enabling this test.")

    settings = get_settings()
    context = AgentContext(
        settings=settings,
        firestore=FirestoreService(settings.gcp_project_id, settings.firestore_database),
        embeddings=EmbeddingsService(settings.gcp_project_id, settings.vertex_ai_location),
        storage=StorageService(settings.gcp_project_id, settings.gcs_bucket),
        bigquery=BigQueryService(settings.gcp_project_id, settings.bq_dataset),
        store_id="store_001",
    )
    session = Session(session_id="test-session", platform="web_widget", store_id="store_001")

    outcome = await IntentDiscoveryAgent(context).run(session=session, query_text="rattan chair")

    assert outcome.results, "expected at least one SKU result"
    assert outcome.event.event_id
    stored_event = await context.firestore.query_events("store_001", time_window_days=1)
    assert any(e.event_id == outcome.event.event_id for e in stored_event)
