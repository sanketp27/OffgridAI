"""tests/integration/test_insight_pipeline.py — end-to-end batch Insight Agent run.

Excluded from the default `pytest` run — see `tests/integration/test_search_flow.py`
for the emulator/dev-project setup this depends on.
"""

from __future__ import annotations

import pytest

from agents.base import AgentContext
from agents.insight import InsightAgent
from config import get_settings
from services.bigquery import BigQueryService
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService
from services.storage import StorageService


@pytest.mark.integration
async def test_insight_generation_creates_stored_insights_from_seeded_events() -> None:
    """Smoke test: seed >= INSIGHT_MIN_EVENTS search events sharing a
    query_text across >= INSIGHT_MIN_SHOPPERS distinct sessions, run the
    batch pipeline, and assert at least one `Insight` document was written
    with a non-empty grounded `brief`.

    Left unimplemented (`pytest.skip`) in the scaffold -- fill in with real
    `FirestoreService.log_event` seeding once the emulator/dev project is
    wired into CI.
    """
    pytest.skip("Wire up the Firestore emulator / dev project before enabling this test.")

    settings = get_settings()
    context = AgentContext(
        settings=settings,
        firestore=FirestoreService(settings),
        embeddings=EmbeddingsService(settings),
        storage=StorageService(settings),
        bigquery=BigQueryService(settings),
        store_id="store_001",
    )

    result = await InsightAgent(context).run(time_window_days=7)

    assert result["insights"], "expected at least one insight to be generated"
    assert all(i.brief for i in result["insights"]), "every insight must have a grounded brief"


@pytest.mark.integration
async def test_insufficient_events_returns_empty_with_reason() -> None:
    """Below `INSIGHT_MIN_EVENTS`, the pipeline must skip clustering
    entirely rather than surface noisy, low-confidence insights.
    """
    pytest.skip("Wire up the Firestore emulator / dev project before enabling this test.")
