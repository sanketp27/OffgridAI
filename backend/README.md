# OffGrid AI — Backend Scaffold (Common / Core Infrastructure Layer)

This is **only** the shared, system-level foundation described in the
backend implementation plan — configuration, logging, retry, exception
handling, and the four GCP clients (Firestore, Vector Search, Gemini,
BigQuery). It deliberately contains **no application/business logic**:
no routers, no agents, no models, no `main.py`. Those go in separate
tickets and import from here.

```
offgrid-backend/
├── .env.example          # every setting this scaffold reads, documented
├── .gitignore
├── pyproject.toml        # dependencies for this layer only
├── config.py             # single source of truth: Settings, loaded from .env
├── core/
│   ├── __init__.py
│   ├── logging.py        # structlog -> Cloud Logging-compatible JSON
│   ├── retry.py          # tenacity backoff+jitter for GCP/Vertex AI calls
│   └── exceptions.py     # typed exception hierarchy + traceback capture
└── services/
    ├── __init__.py
    ├── _genai_client_factory.py  # shared google-genai Client construction
    ├── firestore_client.py       # the db client: async CRUD helpers
    ├── vector_search.py          # Firestore-native + Vertex AI Vector Search (stretch)
    ├── gemini_client.py          # Gemini Flash/Pro chat + JSON-mode generation
    ├── embeddings_client.py      # batched Gemini embeddings
    └── bigquery_client.py        # parameterized insert/query helpers
```

## Setup

```bash
cd offgrid-backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

cp .env.example .env
# edit .env: at minimum set GCP_PROJECT_ID; for local dev without full GCP
# credentials, set USE_VERTEX_AI=false and GEMINI_API_KEY=<your key>
```

Everything downstream (routers, agents, scripts) should do:

```python
from config import get_settings
from services.firestore_client import get_firestore_client
from services.vector_search import get_vector_search_client
from services.gemini_client import get_gemini_client
from services.embeddings_client import get_embeddings_client
from services.bigquery_client import get_bigquery_client
```

— never construct GCP SDK clients directly, and never read `os.environ`
directly. `config.py` is the only place a collection name, model name, or
connection string is allowed to be hardcoded.

## Design decisions worth knowing before you build on this

- **`google-genai`, not `vertexai.generative_models`.** The legacy
  generative-AI modules that used to ship inside `google-cloud-aiplatform`
  were deprecated on 2025-06-24 and are being removed. `gemini_client.py`
  and `embeddings_client.py` both go through the current, unified
  `google-genai` SDK, which works against Vertex AI *or* the public
  Gemini Developer API depending on `settings.use_vertex_ai`
  (`services/_genai_client_factory.py`).
- **Vector search score direction.** Firestore's `DistanceMeasure.COSINE`
  returns a *distance* (`1 - similarity`), not a similarity. If you ever
  bypass `VectorSearchClient` and call `find_nearest` directly, remember
  to convert — `vector_search.py` does this once, centrally, so every
  caller compares against `vector_match_threshold_exact` /
  `_near` on the same "higher is better" scale used throughout the plan.
- **Async-first, sync SDKs wrapped.** Firestore and `google-genai` have
  native async clients (`firestore.AsyncClient`, `client.aio.models.*`),
  used directly. `google-cloud-bigquery` and (for the Vertex AI Vector
  Search stretch backend) `google-cloud-aiplatform` are sync-only, so
  those specific calls are offloaded via `asyncio.to_thread` rather than
  blocking the event loop.
- **Retry is opt-in per call, not global.** Every client method that
  makes a single outbound network call is decorated with
  `@retry_gcp_call()` (exponential backoff + jitter, only on transient
  errors — `ResourceExhausted`, `ServiceUnavailable`, `DeadlineExceeded`,
  etc. — never on `PermissionDenied`/`NotFound`/validation errors, which
  fail immediately). Tuning lives in `.env`
  (`RETRY_MAX_ATTEMPTS`, `RETRY_INITIAL_WAIT_SECONDS`, ...).
- **Exceptions never leak raw SDK types.** Every client method wraps its
  body in `core.exceptions.error_boundary`, which logs a full structured
  traceback (`structlog.processors.dict_tracebacks` — queryable as JSON
  fields in Cloud Logging, not a flat string) and re-raises as a typed
  `FirestoreError` / `GeminiError` / `EmbeddingError` / `VectorSearchError`
  / `BigQueryError`. Application code can catch one family
  (`DependencyError`) without importing `google.api_core.exceptions`.
- **Model names are config, not constants.** `GEMINI_FLASH_MODEL`,
  `GEMINI_PRO_MODEL`, and `GEMINI_EMBEDDING_MODEL` in `.env` default to
  the model IDs named in the ticket specs. Vertex AI model availability
  changes over time — verify against the Model Garden for your project
  before deploying, and change `.env`, never the client code.

## Verification performed while building this scaffold

- All modules import cleanly and byte-compile (`python -m py_compile`).
- `ruff check` passes with zero warnings.
- Every `services/*Client` was instantiated end-to-end against the real,
  installed GCP SDKs (with a locally-generated throwaway service-account
  key for credential wiring — no real GCP project or network calls
  involved) to confirm constructor wiring, config plumbing, and import
  paths are all correct.
- `core/retry.py`'s backoff decorator was verified against a function
  that raises `google.api_core.exceptions.ServiceUnavailable` twice
  before succeeding (confirms it retries and eventually returns the
  result), and against `PermissionDenied` (confirms non-retryable errors
  fail on the first attempt instead of burning the retry budget).
- `core/logging.py` was verified in both JSON mode (`LOG_JSON=true`) and
  console mode, including an exception logged with
  `logger.exception(...)`, confirming the structured-traceback processor
  works.

None of this exercised real GCP/Vertex AI endpoints — that requires a
real project, credentials, and (for `vector_search.py`) a populated
catalog with embeddings, none of which exist yet at this stage of the
build.
