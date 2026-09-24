# OffGrid AI — Backend

Platform-agnostic retail intelligence backend: conversational product discovery,
fit-check return prevention, associate-facing return intelligence, and
merchant insights — built on FastAPI, the Google Agent Development Kit (ADK),
and Vertex AI (Gemini + Embeddings), with Firestore/BigQuery/Cloud Storage as
the data layer. See `architecture.md` for the full system diagram and
`backend_implementation_plan.md` / `ticket_specs.md` for the specs this
scaffold implements against.

## Project layout

```
main.py                    FastAPI app factory — entry point (`uvicorn main:app`)
config.py                  Settings singleton — every tunable constant lives here
dependencies.py            Auth (Firebase), role guards, service singletons

routers/                   HTTP layer — one module per resource area
  search.py                  /search, /search/refine, /search/voice, /session/{id}
  fit_check.py                /fit-check, /follow-up/{session_id}
  return_intel.py             /return, /return/{id}/confirm
  insights.py                  /insights, /insights/generate, /insights/chat, /events/aggregate
  catalog.py                   /catalog/{sku_id}, /catalog/import, /catalog/import/{job_id}

agents/                     The agent mesh — Orchestrator + specialists (Google ADK)
  base.py                     Shared Agent interface + Gemini client wrapper
  orchestrator.py             Sole entry point from routers into the mesh
  discovery.py                 Intent + Discovery Agent (search)
  discovery_refinement.py      Refinement mode (iterative narrowing)
  fit_check.py                 Fit-Check Agent (return-prone SKU clarifier)
  return_intel.py              Return Intelligence Agent (2-stage: vision + code)
  insight.py                   Insight Agent, batch mode (merchant analytics)
  insight_chat.py              Insight Agent, chat mode ("ask your data")
  catalog_import.py            Catalog Import Agent, 4-stage pipeline

models/                     Typed Firestore document models (Pydantic v2)
services/                   Infrastructure wrappers (Firestore, Embeddings, Storage,
                             BigQuery, web Crawler) — the only layer that imports
                             the Google Cloud SDKs directly
scripts/                    Standalone entrypoints — seeding, embedding backfill,
                             the BigQuery mirror Cloud Function, the catalog-import
                             Cloud Run Job runner
tests/
  unit/                       Fast, no-network tests of deterministic agent logic
  integration/                Stubs requiring a live/emulated Firestore + Vertex AI
                               (excluded by default — see pyproject.toml)
```

## Common/core infrastructure layer (`core/`)

`core/` is a shared foundation folded into this project from a separate
infrastructure scaffold, sitting underneath `services/`:

```
core/
  logging.py     structlog -> Cloud Logging-compatible structured JSON,
                 with queryable (not flattened) tracebacks and
                 request/session context binding
  retry.py       tenacity exponential backoff + jitter for every outbound
                 GCP/Vertex AI call, tuned via Settings, retrying only
                 transient errors (never PermissionDenied/NotFound/bad
                 requests, which fail immediately instead of burning the
                 retry budget)
  exceptions.py  typed exception hierarchy (FirestoreError, GeminiError,
                 EmbeddingError, BigQueryError, StorageError, ...) so
                 routers/agents catch one family instead of importing
                 google.api_core.exceptions everywhere, plus
                 error_boundary/capture_exception for structured
                 traceback logging at every service call site
```

Every `services/*Service` class takes a single `Settings` instance in its
constructor (`FirestoreService(settings)`, `EmbeddingsService(settings)`,
etc.) rather than individual positional args, and every outbound network
call goes through `@retry_gcp_call()`/`@retry_gemini_call()` +
`error_boundary(...)`.

## Client-freshness audit (performed during this integration)

When the application layer (agents/routers/models/services) was merged
with the common/core scaffold, every GCP/Vertex AI/FastAPI client call was
checked against current SDK guidance. Two centralized, real issues were
found and fixed:

- **`agents/base.py`'s `GeminiClient` and `services/embeddings.py`'s
  `EmbeddingsService`** were built on `vertexai.generative_models` /
  `vertexai.language_models` — the generative-AI module set inside
  `google-cloud-aiplatform` that Google deprecated on 2025-06-24 and is
  removing. Both are rewritten against `google-genai`
  (`services/_genai_client_factory.py`), the current unified SDK for
  Gemini on Vertex AI or the public Developer API.
- **`services/firestore.py`** used the positional `.where(field, op,
  value)` form throughout, which now raises `UserWarning: Detected
  filter using positional arguments. Prefer using the 'filter' keyword
  argument instead.` on every call (confirmed live against
  `google-cloud-firestore` 2.31). Replaced with `filter=FieldFilter(...)`
  everywhere. The native vector-search path was also recomputing cosine
  similarity in Python from the returned `embedding` field; it now reads
  the match distance directly via `find_nearest(...,
  distance_result_field=...)`, saving a redundant computation and keeping
  the distance -> similarity conversion in one documented place.

Two smaller, real bugs were also fixed while auditing adjacent code:

- `services/bigquery.py`'s `query()` was synchronous but called without
  `await` from an `async def` FastAPI route (`routers/insights.py`),
  blocking the event loop for the query's duration. It's now `async`,
  offloading the blocking SDK call via `asyncio.to_thread`.
- `services/storage.py`'s `generate_signed_url()` only worked against a
  local service-account key file — unmodified, it raises
  `AttributeError: you need a private key to sign credentials` under
  Cloud Run's metadata-server credentials (no private key). It now signs
  via the IAM API using the runtime credentials' service-account email +
  a refreshed access token, which works in both environments.

`main.py` was also moved from FastAPI's deprecated `@app.on_event("startup")`
to the `lifespan` context-manager pattern while it was being updated for
the new settings-driven service constructors.



```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in a real GCP_PROJECT_ID etc.
```

Run the API:

```bash
uvicorn main:app --reload
# -> http://localhost:8000/docs (OpenAPI UI)
# -> http://localhost:8000/health
```

Run the unit tests (fast, no GCP access required):

```bash
pytest                       # unit tests only (default; see pyproject.toml)
pytest --cov=agents --cov=models --cov=services
```

Run integration tests (requires a Firestore emulator or a dev GCP project —
see the module docstrings under `tests/integration/` for setup notes; they
are `pytest.skip`-guarded until wired up):

```bash
gcloud emulators firestore start &
export FIRESTORE_EMULATOR_HOST=localhost:8080
pytest tests/integration -m integration
```

## Design principles this scaffold enforces

- **Numbers never come from the LLM.** Every count, percentage, score
  threshold, and disposition decision a merchant or shopper sees is computed
  by plain Python (see `agents/insight.py`, `agents/return_intel.py`,
  `agents/fit_check.py`). Gemini is used only for extraction, semantic
  clustering, and grounded prose generation — never arithmetic.
- **One vector-search code path.** `services/firestore.py`'s
  `vector_search_catalog` is the only place catalog similarity search
  happens; both fresh and refined searches route through it.
- **The Orchestrator is the only cross-agent entry point.** Agents never
  call each other directly (`agents/orchestrator.py`'s `ROUTING` table is
  the living map of event type -> agent).
- **Every integration seam is isolated and swappable.** Gemini/Vertex AI
  calls live behind narrow, mockable methods (e.g.
  `IntentDiscoveryAgent._extract_intent`,
  `ReturnIntelligenceAgent.grade_condition`) with clearly documented
  deterministic fallbacks, so the whole app runs and is testable end-to-end
  before every live model integration is wired up.

## Deployment (Cloud Run — see `backend_implementation_plan.md` §10.2)

```bash
docker build -t offgrid-backend .
gcloud run deploy offgrid-api --image <image> --region us-central1 \
  --set-env-vars GCP_PROJECT_ID=<project>,ENV=production ...
```

The same image backs the `catalog-import-runner` Cloud Run Job — deploy it
with the container command overridden to
`python -m scripts.catalog_import_runner --job-id "$JOB_ID"` instead of the
Dockerfile's default `uvicorn` command.

The Firestore -> BigQuery event mirror (`scripts/bq_mirror_handler.py`)
deploys separately as a 2nd-gen Cloud Function with an Eventarc Firestore
trigger on the `events` collection (`--entry-point=handler`).

## What's stubbed vs. real

Every piece of **deterministic business logic** described in the
Implementation Plan is fully implemented and unit-tested: match-quality
thresholds, fit-check triggers/classification, return-risk scoring,
disposition rules, insight trend/urgency/signal-classification math, and
catalog-import validation/confidence/dedup.

Every **live Gemini/Vertex AI call site** is isolated behind a narrow method
with a clearly commented, working deterministic fallback (so the app runs
end-to-end without credentials) — search for `Stubbed` / `production:` in
`agents/*.py` docstrings for the exact swap points once Vertex AI access is
configured for a given environment.
