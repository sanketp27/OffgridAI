# OffGrid AI — Backend Implementation Plan
**Role: Solutions Architecture + Project Management**
**Scope: Backend Only | Python + Google Cloud (Non-negotiable)**
**Frontend: Next.js (out of scope for this document)**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Stakeholders & Access Levels](#2-stakeholders--access-levels)
3. [Technology Stack (Backend)](#3-technology-stack-backend)
4. [GCP Service Map](#4-gcp-service-map)
5. [IAM & Identity Architecture](#5-iam--identity-architecture)
6. [Data Structures](#6-data-structures)
7. [API Contract](#7-api-contract)
8. [Agent Architecture](#8-agent-architecture)
9. [System Flows (Backend)](#9-system-flows-backend)
10. [Infrastructure Layout](#10-infrastructure-layout)
11. [Implementation Phases & Milestones](#11-implementation-phases--milestones)
12. [Environment Strategy](#12-environment-strategy)
13. [Non-Functional Requirements](#13-non-functional-requirements)
14. [Risk Register](#14-risk-register)

---

## 1. Executive Summary

OffGrid AI is a platform-agnostic retail intelligence layer. The backend closes the gap between customer shopping failures (zero-result searches, wrong-fit returns, stockouts) and structured merchant actions. Every customer interaction — successful or not — is logged to a shared event schema that the Insight Agent transforms into prioritized, revenue-quantified merchant briefs.

**Core backend responsibility:** receive events from any surface (JS widget, Next.js frontend, mobile SDK, webhooks), route them through a multi-agent reasoning mesh powered by Vertex AI Gemini, persist all state in Firestore, mirror analytics to BigQuery, and expose clean REST endpoints for both consumer-facing and merchant-facing operations.

**Non-negotiable constraints:**
- Python everywhere (FastAPI for the API layer, Python agents via Google ADK)
- Google Cloud exclusively for infrastructure (Vertex AI, Cloud Run, Firestore, BigQuery, Cloud Storage, Firebase Auth, Eventarc, Secret Manager)

---

## 2. Stakeholders & Access Levels

### 2.1 Human Stakeholders

| Stakeholder | Role | System Persona | Backend Access |
|---|---|---|---|
| **Merchant** | Retail store owner / manager | `merchant` | Read: insights, events aggregates. Write: none directly — dashboard triggers `POST /insights/generate` |
| **Store Associate** | In-store staff handling returns | `associate` | Write: `POST /return` (photo upload + order_id). Read: disposition result for their own submitted return |
| **Shopper** | End customer on any commerce surface | `shopper` | Write: `POST /search`, `POST /fit-check`. Read: search results, fit-check question |
| **Platform Admin** | OffGrid internal team | `admin` | Full read/write on all collections. Can re-embed catalog, trigger bulk insight runs, manage secrets |
| **Data Analyst** | OffGrid / merchant analyst | `analyst` | Read-only on BigQuery event mirror. No Firestore direct access |

### 2.2 System Stakeholders (Non-Human)

| System | Role | Auth Mechanism |
|---|---|---|
| **Cloud Run API Service** | Hosts FastAPI — the sole ingress for all external calls | Service Account `offgrid-api-sa` with least-privilege roles |
| **Agent Workers (Cloud Run)** | Each agent runs as a Cloud Run job/service invoked by the Orchestrator | Service Account `offgrid-agent-sa` |
| **Eventarc Trigger** | Mirrors Firestore `events` writes to BigQuery | Managed service account (Google-managed) |
| **Cloud Scheduler** | Triggers nightly Insight batch run | Service Account `offgrid-scheduler-sa` |
| **Firebase Auth** | Issues JWTs to shoppers, associates, merchants | Google-managed |
| **Next.js Frontend** | Calls REST API with Firebase Auth bearer tokens | `shopper` / `associate` / `merchant` role encoded in custom claims |

---

## 3. Technology Stack (Backend)

### 3.1 Core Runtime

| Layer | Technology | Version / Notes |
|---|---|---|
| Language | Python | 3.12 |
| API Framework | FastAPI | 0.115.x — async-first, OpenAPI auto-docs |
| ASGI Server | Uvicorn | Behind Google's Cloud Run managed ingress |
| Agent Orchestration | Google Agent Development Kit (ADK) | Python SDK — `google-adk` |
| LLM Provider | Vertex AI (Gemini) | Flash 3.6 for interactive agents; Pro 3.6 for batch Insight |
| Dependency Management | `uv` | Lockfile committed; reproducible builds |
| Type Checking | `mypy` | Strict mode on all agent and model code |
| Testing | `pytest` + `pytest-asyncio` | Unit + integration; no mocks on the Firestore path |
| Linting | `ruff` | Single linter replacing flake8/isort/pyupgrade |
| Containerization | Docker | Multi-stage build; non-root user in final image |

### 3.2 Google Cloud SDKs (Python)

| SDK | Purpose |
|---|---|
| `google-cloud-firestore` | Firestore reads/writes, vector search |
| `google-cloud-aiplatform` | Vertex AI Gemini calls, embeddings |
| `google-cloud-storage` | Return photo / catalog image upload |
| `google-cloud-bigquery` | Insight analytics queries |
| `firebase-admin` | Server-side Firebase Auth token verification |
| `google-cloud-secret-manager` | Runtime secret loading (API keys, service account creds) |

### 3.3 Key Python Libraries

| Library | Purpose |
|---|---|
| `pydantic` v2 | Request/response models, strict validation |
| `tenacity` | Retry logic for Vertex AI rate-limit responses |
| `numpy` | Cosine similarity scoring for vector search |
| `structlog` | Structured JSON logging (Cloud Logging-compatible) |
| `httpx` | Async HTTP client — inter-service calls + URL crawling |
| `beautifulsoup4` | HTML parsing for URL crawl (link extraction + text stripping) |
| `urllib.robotparser` | robots.txt compliance during URL crawl (stdlib) |
| `pandas` | Excel/CSV parsing for catalog import |
| `openpyxl` | Excel `.xlsx` backend for pandas |
| `pymupdf` (`fitz`) | PDF page splitting + embedded-image extraction |

---

## 4. GCP Service Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Google Cloud Project                          │
│                                                                     │
│  ┌──────────────┐     ┌──────────────────────────────────────────┐  │
│  │ Firebase Auth│     │            Cloud Run                     │  │
│  │  JWT issuance│     │  ┌────────────────┐  ┌────────────────┐  │  │
│  └──────┬───────┘     │  │  FastAPI API   │  │  Agent Workers │  │  │
│         │             │  │  (offgrid-api) │  │  (offgrid-agent│  │  │
│         └─────────────►  └───────┬────────┘  └───────┬────────┘  │  │
│                        └─────────┼────────────────────┼───────────┘  │
│                                  │                    │             │
│  ┌───────────────────────────────▼────────────────────▼──────────┐  │
│  │                        Data Layer                              │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │  │
│  │  │  Firestore   │  │Cloud Storage │  │      BigQuery        │ │  │
│  │  │  (primary)   │  │ (images)     │  │   (event mirror)     │ │  │
│  │  └──────┬───────┘  └──────────────┘  └──────────────────────┘ │  │
│  │         │ Eventarc trigger                                      │  │
│  └─────────┼─────────────────────────────────────────────────────┘  │
│            └─────────────────────────────────────────────────────►  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                  Vertex AI                                     │  │
│  │  Gemini Flash (interactive)  ·  Gemini Pro (batch insight)    │  │
│  │  Gemini Embeddings (gemini-embedding-2)                       │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Secret Manager · Cloud Scheduler · Artifact Registry · Cloud Logging│
└─────────────────────────────────────────────────────────────────────┘
```

| Service | Plan A Config | Justification |
|---|---|---|
| Cloud Run (API) | 1 CPU, 1 GB RAM, min-instances=1 | Prevents cold starts during demo/judges review |
| Cloud Run (Agents) | 2 CPU, 2 GB RAM, request-timeout=120s | Gemini calls + vector search within a single request |
| Firestore | Native mode, `nam5` multi-region | Single source of truth; vector search built-in |
| Cloud Storage | Standard class, `us-central1` | Return photos + catalog images; CORS locked to API domain |
| BigQuery | `us` multi-region dataset | Event mirror; append-only |
| Vertex AI | `us-central1` | Gemini Flash + Pro + gemini-embedding-2 |
| Secret Manager | Regional `us-central1` | API service account key, Vertex AI credentials |
| Artifact Registry | `us-central1` | Docker image store for Cloud Run deploys |
| Cloud Scheduler | — | Nightly insight batch (cron: `0 2 * * *`) |
| Eventarc | Firestore → BigQuery trigger | Mirror events collection writes automatically |

---

## 5. IAM & Identity Architecture

### 5.1 Service Accounts

| SA Name | Bound To | Roles Granted |
|---|---|---|
| `offgrid-api-sa` | Cloud Run API service | `roles/datastore.user`, `roles/storage.objectAdmin`, `roles/aiplatform.user`, `roles/secretmanager.secretAccessor`, `roles/run.invoker` (to trigger catalog import jobs) |
| `offgrid-agent-sa` | Cloud Run agent workers | `roles/datastore.user`, `roles/aiplatform.user`, `roles/storage.objectViewer` |
| `offgrid-import-sa` | Cloud Run Job `offgrid-catalog-import` | `roles/datastore.user`, `roles/storage.objectAdmin`, `roles/aiplatform.user` — storage.objectAdmin needed to write extracted page JSON and the final report |
| `offgrid-scheduler-sa` | Cloud Scheduler jobs | `roles/run.invoker` (can invoke the insight batch endpoint only) |
| `offgrid-bq-writer-sa` | Eventarc / Dataflow | `roles/bigquery.dataEditor` on the events dataset only |

### 5.2 Firebase Auth Custom Claims → Backend Roles

Firebase Auth issues a JWT. The API server verifies it server-side via `firebase-admin`. The `role` custom claim maps to backend authorization:

```python
# Decoded token example
{
  "uid": "abc123",
  "email": "merchant@store.com",
  "role": "merchant",          # custom claim set at registration
  "store_id": "store_001"      # custom claim for multi-tenant scoping
}
```

| Firebase Role Claim | Allowed API Operations |
|---|---|
| `shopper` | `POST /search`, `POST /fit-check`, `GET /session/{session_id}` |
| `associate` | All shopper ops + `POST /return` |
| `merchant` | `GET /insights`, `POST /insights/generate`, `GET /events/aggregate`, `GET /dashboard` |
| `admin` | All endpoints + `POST /catalog/seed`, `POST /catalog/embed`, `DELETE /events` |

### 5.3 Request Auth Flow

```
Next.js / Widget
  → Firebase Auth sign-in (client-side)
  → Firebase issues JWT (RS256, 1h TTL)
  → Client sends JWT in Authorization: Bearer <token>
  → FastAPI dependency `verify_token()`:
      firebase_admin.auth.verify_id_token(token)
      → validates signature, expiry, audience
      → returns decoded claims dict
  → Role-guard dependency `require_role(["merchant"])`
      → checks `claims["role"]` ∈ allowed_roles
      → raises HTTP 403 otherwise
```

---

## 6. Data Structures

### 6.1 Firestore Collections

All documents use Firestore's auto-generated IDs unless noted. Timestamps are Firestore `SERVER_TIMESTAMP`.

---

#### `sessions` Collection

Represents one shopper interaction session. Created on first search. Maintained across multiple search/fit-check turns.

```python
class Session(BaseModel):
    session_id: str           # Firestore document ID (UUID v4)
    platform: str             # "web_widget" | "mobile" | "messaging" | "pos"
    user_id: str | None       # Firebase UID if authenticated; null for anonymous
    store_id: str             # Merchant's store identifier
    created_at: datetime
    last_active_at: datetime
    cart: list[CartItem]      # Current cart state
    intent_history: list[StructuredIntent]  # All parsed intents in session

class CartItem(BaseModel):
    sku_id: str
    variant_id: str | None
    quantity: int
    fit_check_resolution: str | None  # "confirmed" | "size_changed" | "abandoned"

class StructuredIntent(BaseModel):
    category: str
    attributes: dict[str, str]
    budget: float | None
    use_case: str | None
    urgency: str | None
    raw_input_type: str       # "text" | "image" | "voice"
```

---

#### `catalog` Collection

One document per SKU. Immutable after seeding for the demo; in production would be synced from merchant PIM.

```python
class SKU(BaseModel):
    sku_id: str               # Firestore document ID (e.g. "SKU-042")
    name: str
    description: str
    category: str             # "footwear" | "apparel" | "home_goods" | "electronics"
    subcategory: str | None
    price: float
    currency: str             # "INR" | "USD"
    stock: int                # Total available (demo: static)
    return_rate: float        # 0.0–1.0; drives Fit-Check trigger
    image_url: str            # Cloud Storage signed URL or public CDN URL
    attributes: dict[str, str]  # {"material": "rattan", "color": "natural"}
    embedding: list[float]    # Gemini gemini-embedding-2 vector (768-dim)
    store_availability: dict[str, int]  # {"store_001": 5, "store_002": 0}
    is_return_prone: bool     # Derived: category in ["footwear","apparel"] AND return_rate > 0.2
    created_at: datetime
    updated_at: datetime
```

**Firestore Vector Index**: `embedding` field indexed as a vector field with cosine distance metric and dimension=768.

---

#### `events` Collection

Append-only. One document per atomic customer action. Never updated after write.

```python
class Event(BaseModel):
    event_id: str             # Firestore document ID (UUID v4)
    session_id: str           # FK → sessions
    user_id: str | None
    store_id: str
    platform: str
    type: EventType           # Enum — see below
    sku_id: str | None        # Primary SKU involved
    sku_ids: list[str]        # All SKUs returned (for search events)
    matched: bool             # True only for score >= 0.75
    score: float | None       # Top vector similarity score
    resolution: str | None    # Outcome string — see per-type values
    revenue_at_risk: float    # Computed at write time: price * (1 - matched)
    query_text: str | None    # Original shopper query (for analytics)
    created_at: datetime

class EventType(str, Enum):
    SEARCH = "search"
    SEARCH_REFINED = "search_refined"       # OG-048: iterative refinement turn
    VOICE_SEARCH = "voice_search"           # OG-049: voice/multilingual input
    FIT_CHECK = "fit_check"
    FOLLOW_UP_SENT = "follow_up_sent"       # OG-050: post-purchase fit follow-up triggered
    SUBSTITUTE_ACCEPTED = "substitute_accepted"
    RESCUE_DECLINED = "rescue_declined"
    STOCKOUT_LOST = "stockout_lost"
    RETURN_SUBMITTED = "return_submitted"
    RETURN_CONFIRMED = "return_confirmed"
```

**Resolution values by event type:**

| `type` | `resolution` valid values |
|---|---|
| `search` | `"exact_match"` \| `"near_match"` \| `"no_match"` |
| `search_refined` | `"narrowed"` \| `"new_search"` (refinement reclassified as new query) |
| `voice_search` | `"exact_match"` \| `"near_match"` \| `"no_match"` (same as `search`) |
| `fit_check` | `"confirmed"` \| `"size_changed"` \| `"variant_changed"` \| `"abandoned"` |
| `follow_up_sent` | `"sent"` |
| `substitute_accepted` | `"accepted"` |
| `rescue_declined` | `"declined"` |
| `stockout_lost` | `"abandoned"` |
| `return_submitted` | `"pending_review"` |
| `return_confirmed` | `"restock"` \| `"refurbish"` \| `"liquidate"` \| `"hold_for_review"` |

---

#### `insights` Collection

Written by the Insight Agent. One document per generated brief. Merchant dashboard listens via `onSnapshot`.

```python
class Insight(BaseModel):
    insight_id: str           # Firestore document ID
    store_id: str             # Scoped to merchant
    signal_type: SignalType   # Enum
    label: str                # Human-readable cluster label ("waterproof hiking boots")
    occurrences: int          # Computed in Python, never by LLM
    unique_shoppers: int       # Distinct session_ids in cluster
    trend_pct: float | None   # Period-over-period change; None if insufficient history
    est_revenue_at_risk: float  # occurrences × CVR_CONST × AOV_CONST
    urgency_days: int | None  # Restock-by-date estimate (stock gap signals only)
    brief: str                # Gemini Pro prose — 1–3 sentences, grounded on above fields only
    recommended_action: str   # One-line action string
    generated_at: datetime
    event_ids: list[str]      # Source event IDs — full audit trail

class SignalType(str, Enum):
    STOCK_GAP = "stock_gap"
    DISCOVERABILITY_GAP = "discoverability_gap"
    SIZING_CONFUSION = "sizing_confusion"
    PRICING_GAP = "pricing_gap"
```

---

#### `return_assessments` Collection

Written by the Return Intelligence Agent. One document per return item.

```python
class ReturnAssessment(BaseModel):
    assessment_id: str
    order_id: str
    sku_id: str
    store_id: str
    associate_uid: str          # Firebase UID of submitting associate
    image_gcs_path: str         # Cloud Storage object path
    # --- Photo-derived (Gemini Vision) ---
    condition: str              # "new" | "lightly_used" | "damaged"
    condition_justification: str  # What in the image indicates this
    # --- Order-history-derived (Python code) ---
    return_risk_tier: str       # "low" | "medium" | "high"
    risk_factors: list[str]     # ["bracketing", "rapid_return", "prior_history"]
    # --- Disposition (rule-based, NOT LLM) ---
    recommended_disposition: str  # "restock" | "refurbish" | "liquidate" | "hold_for_review"
    disposition_confirmed: bool   # Set to True only after associate confirms
    confirmed_disposition: str | None  # What associate actually chose
    confirmed_by_uid: str | None
    created_at: datetime
    confirmed_at: datetime | None
```

---

---

#### `follow_up_notifications` Collection

Written by the Fit-Check Agent at purchase time (OG-050). One document per flagged purchase. Never updated — append-only.

```python
class FollowUpNotification(BaseModel):
    notification_id: str          # Firestore document ID
    session_id: str               # FK → sessions
    user_id: str | None           # Firebase UID; null for anonymous
    store_id: str
    sku_id: str                   # Purchased SKU that triggered fit-check
    fit_check_resolution: str     # "confirmed" | "size_changed" — must be one of these; never "abandoned"
    follow_up_message: str        # Gemini Flash prose, grounded on resolution + SKU attributes
    created_at: datetime
    delivered: bool               # True once frontend has fetched it
```

**Trigger rule (Python):** Generated only when a session ends with a `fit_check` event whose resolution is `confirmed` or `size_changed`. Never generated for `abandoned`.

**Content differentiation (per OG-050 AC):**
- `size_changed` → message references the specific size swap + a sizing tip grounded in the SKU's fit pattern
- `confirmed` → message includes an easy-return reminder + confidence reinforcement grounded in SKU attributes

---

#### `merchant_chat_sessions` Collection

Stores conversation history for the Ask-Your-Data chat feature (OG-051). One document per chat session.

```python
class MerchantChatSession(BaseModel):
    chat_session_id: str          # Firestore document ID (UUID v4)
    store_id: str                 # Scoped to merchant
    merchant_uid: str             # Firebase UID
    created_at: datetime
    last_active_at: datetime
    turns: list[ChatTurn]         # Ordered list of all turns

class ChatTurn(BaseModel):
    role: str                     # "user" | "assistant"
    message: str
    function_calls: list[FunctionCallLog]  # Which query functions were called
    sources: list[ChatSource]     # Data cited in this turn
    created_at: datetime

class FunctionCallLog(BaseModel):
    function_name: str            # e.g. "get_events_by_filter"
    arguments: dict               # Arguments passed
    result_summary: str           # Human-readable summary of what was returned

class ChatSource(BaseModel):
    source_type: str              # "event_aggregate" | "insight" | "sku"
    label: str                    # e.g. "fit_check events, footwear, last 7d"
    value: str | float            # The actual data cited
```

---

---

#### `catalog_import_jobs` Collection

Tracks async catalog-import pipeline runs. One document per import job, updated as the pipeline progresses through stages.

```python
class CatalogImportJob(BaseModel):
    job_id: str                   # Firestore document ID (UUID v4)
    store_id: str
    initiated_by_uid: str         # Firebase UID (admin role required)
    input_type: str               # "url" | "pdf" | "image" | "excel" | "csv"
    input_source: str             # URL string, or GCS object path for uploaded files
    crawl_depth: int              # Applicable when input_type == "url"; 1–3
    dry_run: bool                 # True → normalize + preview only; do not write to catalog
    status: ImportStatus
    progress: ImportProgress
    result: ImportResult | None   # Populated on status == "done"
    error_message: str | None     # Populated on status == "failed"
    created_at: datetime
    completed_at: datetime | None

class ImportStatus(str, Enum):
    PENDING    = "pending"        # Job created; worker not yet started
    UPLOADING  = "uploading"      # File being written to GCS (URL input: crawling)
    EXTRACTING = "extracting"     # LLM extracting raw product entities
    NORMALIZING = "normalizing"   # Converting raw entities to SKU schema
    DEDUPLICATING = "deduplicating" # Checking against existing catalog
    EMBEDDING  = "embedding"      # Generating Gemini embeddings for new SKUs
    WRITING    = "writing"        # Committing SKU documents to Firestore
    DONE       = "done"
    FAILED     = "failed"

class ImportProgress(BaseModel):
    pages_crawled: int            # URL input only
    raw_entities_found: int       # Total product-like entities extracted
    skus_normalized: int          # Entities successfully converted to SKU schema
    skus_deduplicated: int        # Skipped — already in catalog
    skus_invalid: int             # Failed validation — written to error_details
    skus_added: int               # Actually committed to Firestore catalog
    embeddings_generated: int

class ImportResult(BaseModel):
    skus_added: int
    skus_skipped_duplicate: int
    skus_skipped_invalid: int
    sample_sku_ids: list[str]     # First 5 added SKU IDs for spot-checking
    error_details: list[dict]     # Per-entity errors with raw data for debugging
    gcs_report_path: str          # Full JSON report written to Cloud Storage
```

---

### 6.2 BigQuery Dataset: `offgrid_events`

Mirror of Firestore `events` for SQL analytics. Eventarc writes to this automatically.

**Table: `events`**

| Column | Type | Notes |
|---|---|---|
| `event_id` | STRING | PK |
| `session_id` | STRING | |
| `user_id` | STRING NULLABLE | |
| `store_id` | STRING | Partition key |
| `platform` | STRING | |
| `type` | STRING | EventType enum value |
| `sku_id` | STRING NULLABLE | |
| `sku_ids` | ARRAY<STRING> | |
| `matched` | BOOL | |
| `score` | FLOAT64 NULLABLE | |
| `resolution` | STRING NULLABLE | |
| `revenue_at_risk` | FLOAT64 | |
| `query_text` | STRING NULLABLE | |
| `created_at` | TIMESTAMP | Clustering column |

Partitioned by `DATE(created_at)` and clustered by `store_id, type`.

---

### 6.3 Cloud Storage Bucket Structure

Bucket: `offgrid-ai-assets`

```
offgrid-ai-assets/
├── catalog/
│   └── images/
│       └── {sku_id}.jpg                    # Product images (public-read)
├── returns/
│   └── {store_id}/
│       └── {assessment_id}.jpg             # Return photos (private; signed URL for associate)
├── shelf/
│   └── {store_id}/
│       └── {timestamp}.jpg                 # Shelf photos (future: planogram compliance)
└── imports/
    └── {store_id}/
        └── {job_id}/
            ├── source.<ext>                # Original uploaded file (PDF/image/xlsx/csv)
            ├── extracted_pages/
            │   └── page_{n}.json          # RawPage JSON, one file per page/row (debug)
            └── report.json                # Final import report with error_details + sku_ids
```

**Access policy by prefix:**
- `catalog/images/` — public-read (no auth; served directly to shopper widget)
- `returns/` — private; associate accesses via V4 signed URL (1h TTL, scoped to `assessment_id`)
- `imports/` — private; admin only; `source.*` and `report.json` accessible via signed URL

---

## 7. API Contract

**Base URL:** `https://api.offgrid.ai` (Cloud Run managed domain)
**Auth:** `Authorization: Bearer <Firebase JWT>` on all endpoints except `/health`
**Content-Type:** `application/json` (except multipart endpoints)

---

### 7.1 Endpoint Inventory

**Core endpoints (Phases 0–4):**

| Method | Path | Role Required | Agent(s) Invoked | Description |
|---|---|---|---|---|
| GET | `/health` | None | None | Liveness check |
| POST | `/search` | `shopper` | Intent + Discovery | Main search entry point (text or image) |
| POST | `/fit-check` | `shopper` | Fit-Check | Submit shopper's fit-check response |
| POST | `/return` | `associate` | Return Intelligence | Upload return photo; get disposition |
| POST | `/return/{id}/confirm` | `associate` | None | Associate confirms/overrides disposition |
| GET | `/insights` | `merchant` | None | Fetch stored insights for store |
| POST | `/insights/generate` | `merchant` | Insight | On-demand insight pipeline run |
| GET | `/events/aggregate` | `merchant` | None | Raw aggregated event stats |
| GET | `/session/{session_id}` | `shopper` | None | Fetch session state |
| POST | `/catalog/embed` | `admin` | Embedding job | Re-embed full catalog |
| GET | `/catalog/{sku_id}` | `shopper` | None | Get single SKU |

**Phase 5A endpoints (feature extensions):**

| Method | Path | Role Required | Agent(s) Invoked | Phase 5A Feature |
|---|---|---|---|---|
| POST | `/search/refine` | `shopper` | Discovery (refinement mode) | OG-048: Iterative refinement |
| POST | `/search/voice` | `shopper` | Intent + Discovery | OG-049: Multilingual & voice-first search |
| GET | `/follow-up/{session_id}` | `shopper` | None (reads Firestore) | OG-050: Post-purchase fit follow-up |
| POST | `/insights/chat` | `merchant` | Insight (chat mode) | OG-051: Ask-your-data merchant chat |

**Catalog Import endpoints (Onboarding feature):**

| Method | Path | Role Required | Agent(s) Invoked | Description |
|---|---|---|---|---|
| POST | `/catalog/import` | `admin` | CatalogImport | Start an import job (URL, PDF, image, Excel, CSV) |
| GET | `/catalog/import/{job_id}` | `admin` | None | Poll job status and progress |
| GET | `/catalog/import/{job_id}/preview` | `admin` | None | Preview first 10 normalized SKU candidates |
| POST | `/catalog/import/{job_id}/confirm` | `admin` | None | Confirm a `dry_run` job — write to Firestore |

---

### 7.2 Request / Response Schemas

#### `POST /search`

**Request (multipart/form-data or JSON):**
```json
{
  "session_id": "uuid-v4-or-null",
  "query_text": "something cozy for the living room under 5000",
  "image_base64": null,
  "store_id": "store_001",
  "platform": "web_widget"
}
```

**Response 200:**
```json
{
  "session_id": "generated-or-existing-uuid",
  "results": [
    {
      "sku_id": "SKU-042",
      "name": "Rattan Armchair",
      "price": 4500,
      "currency": "INR",
      "image_url": "https://storage.googleapis.com/.../SKU-042.jpg",
      "match_score": 0.91,
      "match_explanation": "This rattan armchair matches the cozy, natural style you described and falls within your budget.",
      "match_quality": "exact"
    }
  ],
  "fit_check": {
    "triggered": true,
    "sku_id": "SKU-042",
    "question": "This runs about half a size small — do you usually size up?"
  },
  "event_id": "evt-uuid"
}
```

**`match_quality` values:** `"exact"` (score ≥ 0.75) | `"near"` (0.4–0.75) | `"miss"` (< 0.4)

---

#### `POST /fit-check`

**Request:**
```json
{
  "session_id": "uuid",
  "sku_id": "SKU-042",
  "response_text": "I'll go with 9.5",
  "event_id": "evt-uuid-from-search"
}
```

**Response 200:**
```json
{
  "resolution": "size_changed",
  "new_sku_id": "SKU-042-9.5",
  "cart_updated": true,
  "event_id": "evt-uuid-fitcheck"
}
```

---

#### `POST /return`

**Request (multipart/form-data):**
```
image: <binary>
order_id: "ORD-00123"
store_id: "store_001"
```

**Response 200:**
```json
{
  "assessment_id": "asmt-uuid",
  "condition": "lightly_used",
  "condition_justification": "Item shows minor creasing on the toe box; tags are missing but no visible damage.",
  "return_risk_tier": "high",
  "risk_factors": ["bracketing", "rapid_return"],
  "recommended_disposition": "hold_for_review",
  "requires_confirmation": true
}
```

---

#### `POST /insights/generate`

**Request:**
```json
{
  "store_id": "store_001",
  "time_window_days": 7
}
```

**Response 200:**
```json
{
  "insights": [
    {
      "insight_id": "ins-uuid",
      "signal_type": "stock_gap",
      "label": "waterproof hiking boots under ₹4,000",
      "occurrences": 14,
      "unique_shoppers": 12,
      "trend_pct": 40.0,
      "est_revenue_at_risk": 44.80,
      "urgency_days": 5,
      "brief": "14 shoppers searched for waterproof hiking boots under ₹4,000 this week (↑40% vs last week) and left without buying — roughly ₹45 in weekly revenue at risk. Consider sourcing a matching SKU.",
      "recommended_action": "Source a waterproof hiking boot priced under ₹4,000",
      "generated_at": "2026-09-23T02:00:00Z"
    }
  ],
  "generated_at": "2026-09-23T02:01:23Z",
  "event_count_processed": 47
}
```

---

### 7.3 Phase 5A Endpoint Schemas

#### `POST /search/refine` — Iterative Refinement (OG-048)

Narrows the current result set by a modifier utterance. Does **not** restart the search — it mutates the existing `StructuredIntent` on the session and re-runs retrieval with the updated filters.

**Request:**
```json
{
  "session_id": "existing-uuid",
  "refinement_text": "show me something cheaper",
  "prior_result_sku_ids": ["SKU-042", "SKU-107", "SKU-203"]
}
```

**How the backend classifies the utterance (Python — no LLM call):**
```python
REFINEMENT_SIGNALS = {
    "price_down":   ["cheaper", "lower price", "budget", "affordable", "under"],
    "price_up":     ["higher quality", "premium", "splurge", "more expensive"],
    "style_change": ["bolder", "more minimal", "modern", "classic", "colourful"],
    "new_search":   []  # default if no signal matches — reclassify as fresh /search
}
```

If classified as `new_search`, the backend transparently routes to the existing `/search` path and returns `is_new_search: true` in the response so the frontend can update its UI state.

**Response 200:**
```json
{
  "session_id": "existing-uuid",
  "refinement_applied": "price_down",
  "updated_intent": {
    "category": "home_goods",
    "attributes": {"style": "cozy"},
    "budget": 2500,
    "use_case": null,
    "urgency": null
  },
  "results": [
    {
      "sku_id": "SKU-089",
      "name": "Jute Storage Basket",
      "price": 1800,
      "currency": "INR",
      "image_url": "https://storage.googleapis.com/.../SKU-089.jpg",
      "match_score": 0.83,
      "match_explanation": "Within your revised ₹2,500 budget and similar natural-material style.",
      "match_quality": "exact"
    }
  ],
  "is_new_search": false,
  "fit_check": { "triggered": false },
  "event_id": "evt-uuid-refined"
}
```

**Event logged:** `type: "search_refined"`, `resolution: "narrowed"`, carries `prior_result_sku_ids` as a field for continuity tracking.

---

#### `POST /search/voice` — Multilingual & Voice-First Search (OG-049)

Accepts raw audio. Transcription and language detection happen inside a single Gemini Flash call — no separate translation pipeline. Results and explanations are returned in the shopper's detected language.

**Request (multipart/form-data):**
```
audio: <binary>                # WAV / WebM / OGG — browser MediaRecorder output
session_id: "uuid-or-null"
store_id: "store_001"
platform: "web_widget"
language_hint: "hi"            # BCP-47 code; optional — Gemini detects if omitted
```

**Processing (single Gemini Flash multimodal call):**
```
Input: audio bytes + system prompt instructing:
  1. Transcribe in the original language
  2. Extract StructuredIntent in the same format as /search
  3. Detect language code
  4. Do NOT translate to English — preserve original language throughout
Output: {transcription, detected_language, structured_intent}
```

Then: identical vector search + match-quality routing + grounded explanation path as `/search`. Explanation is generated in `detected_language`.

**Response 200:**
```json
{
  "session_id": "generated-or-existing-uuid",
  "transcription": "पाँच हज़ार रुपये से कम में आरामदायक जूते दिखाओ",
  "detected_language": "hi",
  "results": [
    {
      "sku_id": "SKU-055",
      "name": "Canvas Slip-On Shoes",
      "price": 3999,
      "currency": "INR",
      "image_url": "https://storage.googleapis.com/.../SKU-055.jpg",
      "match_score": 0.88,
      "match_explanation": "ये कैनवास स्लिप-ऑन जूते आरामदायक हैं और आपके ₹5,000 के बजट में आते हैं।",
      "match_quality": "exact"
    }
  ],
  "fit_check": { "triggered": false },
  "event_id": "evt-uuid-voice"
}
```

**Event logged:** `type: "voice_search"`, carries `detected_language` as an extra field.

**Edge case — mixed-language query:** Gemini handles code-switching natively. No special backend logic required; tested explicitly in OG-049 acceptance criteria.

---

#### `GET /follow-up/{session_id}` — Post-Purchase Fit Follow-Up (OG-050)

Returns the pending follow-up notification for a session where a fit-check-flagged purchase occurred. Called by the Next.js frontend at purchase confirmation time. If no follow-up exists (fit-check never triggered, or resolution was `abandoned`), returns `triggered: false` — not an error.

**Request:** No body. `session_id` in path. Bearer token must match session's `user_id` or be `admin`.

**Response 200 — follow-up exists:**
```json
{
  "triggered": true,
  "notification_id": "ntf-uuid",
  "sku_id": "SKU-042",
  "sku_name": "Running Shoes - Size 9",
  "fit_check_resolution": "size_changed",
  "follow_up_message": "You sized up to 9.5 — a great call for this model, which runs narrow. If the fit still feels off after the first wear, our return window is open for 30 days. No rush.",
  "created_at": "2026-09-23T14:22:00Z"
}
```

**Response 200 — no follow-up:**
```json
{
  "triggered": false
}
```

**When the follow-up is generated:** The Fit-Check Agent writes the `follow_up_notifications` document immediately after a `confirmed` or `size_changed` fit-check event is logged — not at the time this GET is called. This endpoint only reads; it never triggers generation. Marks `delivered: true` on the document after returning, so repeated fetches are idempotent.

**Message content rules (enforced in Fit-Check Agent prompt):**
- `size_changed` → references the specific variant change + a sizing tip grounded in the SKU's `attributes` object
- `confirmed` → easy-return reminder + confidence signal grounded in SKU return_rate and attributes
- No invented claims; no generic copy that applies to every product

---

#### `POST /insights/chat` — Ask-Your-Data Merchant Chat (OG-051)

Free-form Q&A for merchants. Gemini Pro uses function-calling over a fixed set of query functions — it cannot issue arbitrary Firestore queries. Every number in the answer is returned by a function call; the LLM narrates and interprets, never computes.

**Request:**
```json
{
  "store_id": "store_001",
  "chat_session_id": "existing-chat-uuid-or-null",
  "message": "Why did fit-check flips spike last week for running shoes?"
}
```

**Available query functions (Gemini function-calling schema):**
```python
CHAT_TOOLS = [
    {
        "name": "get_events_by_filter",
        "description": "Query logged events by type, category, date range.",
        "parameters": {
            "event_type": {"type": "string"},           # EventType enum value
            "category": {"type": "string", "nullable": True},
            "resolution": {"type": "string", "nullable": True},
            "date_range_days": {"type": "integer", "default": 7}
        }
    },
    {
        "name": "get_fit_check_flip_rate",
        "description": "Return flip rate (size_changed / total fit_checks) per SKU for a category.",
        "parameters": {
            "category": {"type": "string"},
            "date_range_days": {"type": "integer", "default": 7}
        }
    },
    {
        "name": "get_signal_by_type",
        "description": "Fetch stored Insight documents filtered by signal_type.",
        "parameters": {
            "signal_type": {"type": "string"},          # SignalType enum value
            "top_n": {"type": "integer", "default": 5}
        }
    },
    {
        "name": "get_top_signals",
        "description": "Return top N insights ranked by est_revenue_at_risk.",
        "parameters": {
            "top_n": {"type": "integer", "default": 5}
        }
    },
    {
        "name": "get_sku_details",
        "description": "Fetch a specific SKU's attributes, return_rate, and stock.",
        "parameters": {
            "sku_id": {"type": "string"}
        }
    }
]
```

**System prompt (excerpt):**
```
You are OffGrid's Merchant Intelligence assistant. Answer the merchant's question using ONLY data returned by the available functions.
RULES:
1. Call a function before stating any number. Never state a count, rate, or dollar figure you did not receive from a function result.
2. If no function can answer the question, say "I don't have that data" — do not guess.
3. Cite your sources: for every number, name the function and the key field it came from.
4. Keep answers to 3 sentences maximum. Lead with the finding, not the method.
```

**Response 200:**
```json
{
  "chat_session_id": "chat-uuid",
  "answer": "Fit-check flips for running shoes hit 62% last week — up from 38% the prior week. The spike is concentrated on SKU-042 (size 9), where 11 of 14 shoppers who answered the fit-check question switched to 9.5. That pattern suggests the size-9 listing's size chart is showing incorrect sizing.",
  "sources": [
    {
      "source_type": "event_aggregate",
      "label": "fit_check events, footwear, last 7d",
      "value": "62% flip rate"
    },
    {
      "source_type": "sku",
      "label": "SKU-042 fit_check breakdown",
      "value": "11/14 size_changed"
    }
  ],
  "unanswerable": false
}
```

**Response 200 — unanswerable question:**
```json
{
  "chat_session_id": "chat-uuid",
  "answer": "I don't have data to forecast next month's sales — I can only report on what's already happened. Would you like to see current revenue-at-risk signals instead?",
  "sources": [],
  "unanswerable": true
}
```

**Chat history:** Each turn is appended to the `merchant_chat_sessions` Firestore document. The full turn history is passed to Gemini on each request so the model has conversation context.

---

### 7.4 Phase 5A Pipeline Extensions to `POST /insights/generate`

OG-052 and OG-053 are not new endpoints — they extend the existing `POST /insights/generate` pipeline. The response schema and endpoint path are unchanged; what changes is the classification logic and two fields that may now be populated.

#### OG-052 — Pricing Gap Signal Type

A fourth `signal_type` classification is added to the rule-based classifier (Python, not LLM):

```python
def classify_signal(cluster: Cluster, catalog: list[SKU]) -> SignalType:
    sku_exists = any(s.sku_id for s in catalog if cluster.label in s.name.lower())

    if not sku_exists:
        return SignalType.STOCK_GAP

    avg_match_score = mean(e.score for e in cluster.events if e.score)

    if avg_match_score < VECTOR_MATCH_THRESHOLD_EXACT:
        return SignalType.DISCOVERABILITY_GAP

    # Item existed and matched well, but still didn't convert
    # Check: did the shopper's stated budget fall below the matched SKU's price?
    budgets = [e.intent.budget for e in cluster.events if e.intent and e.intent.budget]
    matched_prices = [
        next(s.price for s in catalog if s.sku_id == e.sku_id)
        for e in cluster.events if e.sku_id
    ]
    if budgets and matched_prices:
        median_budget = median(budgets)
        median_price = median(matched_prices)
        if median_price > median_budget * 1.20:          # item costs >20% above stated budget
            return SignalType.PRICING_GAP

    # Elevated fit-check flip rate → sizing confusion
    flip_rate = sum(1 for e in cluster.events if e.resolution == "size_changed") / len(cluster.events)
    if flip_rate > 0.35:
        return SignalType.SIZING_CONFUSION

    return SignalType.DISCOVERABILITY_GAP                # safe fallback
```

**Pricing gap insight response shape (example):**
```json
{
  "signal_type": "pricing_gap",
  "label": "yoga mats",
  "occurrences": 9,
  "unique_shoppers": 8,
  "trend_pct": null,
  "est_revenue_at_risk": 32.40,
  "urgency_days": null,
  "brief": "9 shoppers searched for yoga mats with an average budget of ₹800, but the closest match (SKU-077) is priced at ₹1,200 — 50% above their stated budgets. Consider a promotional price or sourcing a lower-cost alternative.",
  "recommended_action": "Run a promotion on SKU-077 or source a yoga mat under ₹900"
}
```

**`recommended_action` by signal type:**

| `signal_type` | `recommended_action` content |
|---|---|
| `stock_gap` | "Source a [label] SKU" |
| `discoverability_gap` | "Review search tags and synonyms for [label]" |
| `sizing_confusion` | "Audit the size chart for [label]" |
| `pricing_gap` | "Run a promotion on [top-matched SKU] or source a lower-priced alternative" |

---

#### OG-053 — Restock-by-Date Urgency

`urgency_days` is populated only for `stock_gap` signals. Formula is computed in Python before the brief is generated; the LLM receives it as a pre-computed integer and narrates it verbatim.

```python
def compute_urgency_days(cluster: Cluster, prior_cluster: Cluster | None) -> int | None:
    if cluster.signal_type != SignalType.STOCK_GAP:
        return None

    if prior_cluster is None or cluster.occurrences < MIN_EVENTS_FOR_URGENCY:
        return None                    # Insufficient history — omit rather than guess

    daily_rate = cluster.occurrences / TIME_WINDOW_DAYS    # e.g. 14 / 7 = 3.6/day
    trend_multiplier = 1 + (cluster.trend_pct / 100) if cluster.trend_pct else 1.0

    # Project forward: at current growth rate, how many days until this signal
    # reaches the HIGH_URGENCY_THRESHOLD (occurrences = 3× current)?
    days_to_threshold = HIGH_URGENCY_THRESHOLD / (daily_rate * trend_multiplier)
    return max(1, round(days_to_threshold))
```

**In the brief:** The LLM prompt receives `urgency_days` and is instructed to include it as-is:
```
If urgency_days is present, include exactly: "at the current pace, consider restocking within about {urgency_days} days."
If urgency_days is null, omit any urgency reference entirely.
```

---

---

### 7.5 Catalog Import Endpoint Schemas

#### `POST /catalog/import` — Start an Import Job

Accepts a URL or an uploaded file (PDF, image, Excel, CSV). Creates a `catalog_import_jobs` document, kicks off the async import worker (Cloud Run Job), and returns `job_id` immediately — the caller polls `GET /catalog/import/{job_id}` for progress.

**Request — URL input (JSON):**
```json
{
  "input_type": "url",
  "url": "https://merchant-store.com/products",
  "crawl_depth": 3,
  "store_id": "store_001",
  "dry_run": false
}
```

**Request — File input (multipart/form-data):**
```
file: <binary>         # PDF / JPEG / PNG / .xlsx / .csv
input_type: "pdf"      # "pdf" | "image" | "excel" | "csv"
store_id: "store_001"
dry_run: false         # true = normalize + preview only; do not write catalog
```

**Validation on receipt:**
- URL input: validate URL format and reachability (HEAD request) before starting job
- File input: validate MIME type matches `input_type`; reject files > 50 MB
- `crawl_depth` clamped to 1–3; defaults to 3

**Processing on receipt:**
```
1. Validate input
2. If file: upload to Cloud Storage at imports/{store_id}/{job_id}/source.<ext>
3. Create catalog_import_jobs document with status: "pending"
4. Invoke Cloud Run Job `offgrid-catalog-import` with job_id as argument (async)
5. Return job_id immediately
```

**Response 202:**
```json
{
  "job_id": "imp-uuid",
  "status": "pending",
  "input_type": "url",
  "input_source": "https://merchant-store.com/products",
  "message": "Import job started. Poll GET /catalog/import/imp-uuid for progress."
}
```

---

#### `GET /catalog/import/{job_id}` — Poll Job Status

**Response 200 — in progress:**
```json
{
  "job_id": "imp-uuid",
  "status": "extracting",
  "input_type": "url",
  "progress": {
    "pages_crawled": 42,
    "raw_entities_found": 0,
    "skus_normalized": 0,
    "skus_deduplicated": 0,
    "skus_invalid": 0,
    "skus_added": 0,
    "embeddings_generated": 0
  },
  "created_at": "2026-09-23T10:00:00Z",
  "completed_at": null
}
```

**Response 200 — completed:**
```json
{
  "job_id": "imp-uuid",
  "status": "done",
  "input_type": "url",
  "progress": {
    "pages_crawled": 87,
    "raw_entities_found": 312,
    "skus_normalized": 289,
    "skus_deduplicated": 14,
    "skus_invalid": 23,
    "skus_added": 275,
    "embeddings_generated": 275
  },
  "result": {
    "skus_added": 275,
    "skus_skipped_duplicate": 14,
    "skus_skipped_invalid": 23,
    "sample_sku_ids": ["SKU-301", "SKU-302", "SKU-303", "SKU-304", "SKU-305"],
    "error_details": [
      {
        "raw_name": "Bundle Pack — no price",
        "reason": "price_missing"
      }
    ],
    "gcs_report_path": "imports/store_001/imp-uuid/report.json"
  },
  "created_at": "2026-09-23T10:00:00Z",
  "completed_at": "2026-09-23T10:03:47Z"
}
```

---

#### `GET /catalog/import/{job_id}/preview` — Preview Normalized SKUs

Only meaningful after `status == "normalizing"` or `"done"` (for `dry_run` jobs). Returns the first 10 normalized SKU candidates so an admin can spot-check before committing.

**Response 200:**
```json
{
  "job_id": "imp-uuid",
  "total_normalized": 289,
  "preview": [
    {
      "candidate_id": "cand-001",
      "name": "Heritage Canvas Tote",
      "category": "accessories",
      "price": 1299.00,
      "currency": "INR",
      "attributes": {"material": "canvas", "color": "natural"},
      "stock": 50,
      "return_rate": 0.05,
      "image_url": "https://merchant-store.com/images/tote-natural.jpg",
      "source_page": "https://merchant-store.com/products/tote",
      "confidence": 0.94
    }
  ]
}
```

`confidence` is a Python-computed score (0–1) based on how many required SKU fields were populated from the source data vs. defaulted. It is never computed by the LLM.

---

#### `POST /catalog/import/{job_id}/confirm` — Confirm a Dry-Run Job

Only valid when `dry_run: true` and `status: "done"`. Triggers the write-to-catalog + embedding stage.

**Request:**
```json
{
  "exclude_candidate_ids": ["cand-003", "cand-017"]
}
```

**Response 200:**
```json
{
  "job_id": "imp-uuid",
  "status": "writing",
  "skus_to_write": 287,
  "skus_excluded": 2,
  "message": "Writing to catalog and generating embeddings. Poll GET /catalog/import/imp-uuid for completion."
}
```

---

## 8. Agent Architecture

### 8.1 Agent Mesh Overview

All agents are Python classes conforming to the Google ADK `Agent` interface. The Orchestrator is the sole entry point — it receives a normalized payload from the FastAPI layer and returns a unified response. Agents never call each other directly.

```
FastAPI Layer
    │
    ▼
Orchestrator Agent
    ├── Intent + Discovery Agent   (Gemini Flash, function-calling)  — /search, /search/voice
    ├── Discovery Agent (Refinement mode)                            — /search/refine
    ├── Fit-Check Agent            (Gemini Flash, function-calling)  — /fit-check, follow-up generation
    ├── Return Intelligence Agent  (Gemini Flash, multimodal)        — /return
    ├── Insight Agent              (Gemini Pro, batch)               — /insights/generate
    └── Insight Agent (Chat mode)  (Gemini Pro, function-calling)    — /insights/chat
```

### 8.2 Agent Definitions

---

#### Orchestrator

**File:** `backend/agents/orchestrator.py`

**Responsibilities:**
- Deserialize the FastAPI request into an `OrchestratorEvent`
- Determine which specialist agent(s) to invoke based on `event.type`
- Maintain session context across turns (loads/saves `Session` from Firestore)
- Aggregate specialist responses into the final API response payload

**Routing table:**
```python
ROUTING = {
    # Core (Phases 0–4)
    "search":              [IntentDiscoveryAgent],
    "fit_check_response":  [FitCheckAgent],
    "return":              [ReturnIntelligenceAgent],
    "insights_generate":   [InsightAgent],

    # Phase 5A extensions
    "search_refine":       [DiscoveryRefinementAgent],   # OG-048
    "voice_search":        [IntentDiscoveryAgent],        # OG-049 — same agent; audio input flag set
    "insights_chat":       [InsightChatAgent],            # OG-051
    # OG-050 follow-up is written by FitCheckAgent inline after fit_check_response;
    # GET /follow-up/{session_id} is a direct Firestore read — no agent invoked
    # OG-052 / OG-053 are pipeline extensions inside InsightAgent — no routing change
}
```

**System prompt:** None — the Orchestrator is pure Python routing logic. It does not call an LLM itself.

---

#### Intent + Discovery Agent

**File:** `backend/agents/discovery.py`

**Model:** `gemini-3.6-flash`

**Tools (Gemini function-calling schema):**
```python
tools = [
    {
        "name": "extract_structured_intent",
        "description": "Parse free-form text or image into a structured shopping intent.",
        "parameters": {
            "category": {"type": "string"},
            "attributes": {"type": "object"},
            "budget": {"type": "number", "nullable": True},
            "use_case": {"type": "string", "nullable": True},
            "urgency": {"type": "string", "nullable": True}
        }
    },
    {
        "name": "vector_search_catalog",
        "description": "Search the SKU catalog by embedding similarity with optional filters.",
        "parameters": {
            "embedding": {"type": "array", "items": {"type": "number"}},
            "category_filter": {"type": "string", "nullable": True},
            "max_price": {"type": "number", "nullable": True},
            "top_k": {"type": "integer", "default": 5}
        }
    },
    {
        "name": "log_search_event",
        "description": "Persist the search event to Firestore.",
        "parameters": {
            "session_id": {"type": "string"},
            "matched": {"type": "boolean"},
            "score": {"type": "number"},
            "sku_ids": {"type": "array", "items": {"type": "string"}},
            "query_text": {"type": "string"}
        }
    }
]
```

**System prompt (excerpt):**
```
You are OffGrid's Discovery Agent. Your only job is to understand what a shopper wants and return the most relevant products from the catalog.

STRICT RULES:
1. You may only describe products retrieved by vector_search_catalog. Never mention features, colors, or attributes not present in a retrieved SKU's data.
2. If no strong match exists, explain the gap honestly and show the closest available products.
3. Never return an empty result — always show something with an explanation.
4. After retrieving results, call log_search_event before returning.
```

**Execution flow:**
```
1. Receive {query_text | image_bytes, session_id, filters}
2. Call extract_structured_intent → StructuredIntent
3. Generate query embedding from intent text via Vertex AI Embeddings
4. Call vector_search_catalog(embedding, filters) → List[SKU]
5. Evaluate top score:
   ├── score >= 0.75 → matched=True, build result cards
   ├── 0.4 <= score < 0.75 → matched=False, near-match explanation
   └── score < 0.4 → matched=False, honest miss + broadest fallback
6. Generate grounded match explanation (one sentence per result)
7. Call log_search_event
8. Check FitCheck trigger condition for top result
9. Return SearchResponse
```

---

#### Fit-Check Agent

**File:** `backend/agents/fit_check.py`

**Model:** `gemini-3.6-flash`

**Trigger condition (Python, NOT LLM):**
```python
def should_trigger(sku: SKU) -> bool:
    RETURN_PRONE_CATEGORIES = {"footwear", "apparel", "electronics_accessories"}
    return sku.category in RETURN_PRONE_CATEGORIES and sku.return_rate > 0.20
```

**Tools:**
```python
tools = [
    {
        "name": "generate_fit_question",
        "description": "Generate one SKU-specific clarifying question about fit or compatibility.",
        "parameters": {
            "sku_id": {"type": "string"},
            "sku_name": {"type": "string"},
            "sku_category": {"type": "string"},
            "return_rate": {"type": "number"},
            "attributes": {"type": "object"}
        }
    },
    {
        "name": "classify_response",
        "description": "Classify shopper's fit-check answer.",
        "parameters": {
            "response_text": {"type": "string"},
            "sku_id": {"type": "string"}
        }
    },
    {
        "name": "log_fit_check_event",
        "description": "Persist fit-check outcome to Firestore.",
        "parameters": {
            "session_id": {"type": "string"},
            "sku_id": {"type": "string"},
            "question": {"type": "string"},
            "resolution": {"type": "string"}
        }
    }
]
```

**Response classification:**
```python
RESOLUTION_MAP = {
    "size_changed": ["I'll go with", "let me take", "give me the"],
    "variant_changed": ["different color", "different model"],
    "confirmed": ["I'm good", "that's fine", "yes", "no change"],
    "abandoned": []  # default if none match within timeout
}
```

---

#### Return Intelligence Agent

**File:** `backend/agents/return_intel.py`

**Model:** `gemini-3.6-flash` (multimodal)

**Two-stage design (per architecture review fix — these stages are ALWAYS separate):**

**Stage 1 — Photo condition grading (Gemini Vision):**
```python
CONDITION_PROMPT = """
Classify the physical condition of the returned item in this photo.
Output ONLY one of: new | lightly_used | damaged
Then provide ONE sentence citing visible evidence in the image.
Do NOT make any claim about fraud, return history, customer behavior, or authenticity.
"""
```

**Stage 2 — Return risk scoring (Python only, NO LLM):**
```python
def compute_return_risk(order_history: list[Order]) -> ReturnRiskResult:
    score = 0
    factors = []
    
    # Bracketing: multiple sizes of same SKU ordered together
    variants_ordered = [o.variant_id for o in order_history if o.sku_id == current_sku_id]
    if len(set(variants_ordered)) > 1:
        score += 30
        factors.append("bracketing")
    
    # Rapid return: returned within 48h of delivery
    if days_held < 2:
        score += 25
        factors.append("rapid_return")
    
    # Prior return history
    past_returns = [o for o in order_history if o.was_returned]
    if len(past_returns) > 2:
        score += 20
        factors.append("prior_history")
    
    tier = "high" if score >= 50 else "medium" if score >= 25 else "low"
    return ReturnRiskResult(tier=tier, factors=factors, score=score)
```

**Disposition rules (Python, NOT LLM):**
```python
DISPOSITION_RULES = {
    ("new", "low"):           "restock",
    ("new", "medium"):        "restock",
    ("new", "high"):          "hold_for_review",
    ("lightly_used", "low"):  "refurbish",
    ("lightly_used", "medium"): "refurbish",
    ("lightly_used", "high"): "hold_for_review",
    ("damaged", "*"):         "liquidate",
}
```

---

#### Insight Agent

**File:** `backend/agents/insight.py`

**Model:** `gemini-3.6-pro` (batch)

**Pipeline (all numeric scoring in Python — zero LLM arithmetic):**

```python
# Step 1: Aggregate raw events (Python)
events = await firestore.query_events(store_id, time_window_days)

# Step 2: Semantic clustering (Gemini Pro — meaning only, no numbers)
CLUSTER_PROMPT = f"""
Group these {len(events)} search queries by meaning into labeled clusters.
Return a JSON array: [{{"label": "...", "query_indices": [0,3,7]}}]
Do not compute counts, trends, or revenue. That is not your job here.
Queries: {json.dumps(query_texts)}
"""
clusters = gemini_pro.generate(CLUSTER_PROMPT, response_format="json")

# Step 3: Code-based scoring (Python only)
for cluster in clusters:
    cluster_events = [events[i] for i in cluster.query_indices]
    cluster.occurrences = len(cluster_events)
    cluster.unique_shoppers = len(set(e.session_id for e in cluster_events))
    cluster.trend_pct = compute_trend(cluster_events, prior_window_events)
    cluster.est_revenue_at_risk = (
        cluster.occurrences * INDUSTRY_CVR * median_aov(cluster_events)
    )
    cluster.urgency_days = compute_urgency(cluster) if cluster.signal_type == "stock_gap" else None

# Step 4: Signal classification (Python rule-based)
for cluster in clusters:
    cluster.signal_type = classify_signal(cluster, catalog)

# Step 5: Brief generation (Gemini Pro — prose only, grounded on step 3 output)
BRIEF_PROMPT = f"""
Write 1-3 sentences in plain language for a retail merchant.
Use ONLY the numbers provided below. Do not compute, estimate, or invent any number.
State the trend only if trend_pct is not null.
End with one concrete action recommendation.

Data: {cluster.model_dump_json()}
"""
cluster.brief = gemini_pro.generate(BRIEF_PROMPT)
```

---

#### Discovery Agent — Refinement Mode (OG-048)

**File:** `backend/agents/discovery_refinement.py`

**Model:** `gemini-3.6-flash`

This is not a separate agent class — it is the `IntentDiscoveryAgent` invoked with a `refinement=True` flag and the session's existing `StructuredIntent` passed in context. No new Gemini call is made to re-parse intent from scratch.

**Execution flow:**
```
1. Load existing StructuredIntent from session (Firestore)
2. Classify refinement utterance (Python pattern match — no LLM):
   ├── price_down   → intent.budget = infer_new_budget(utterance, current_budget)
   ├── price_up     → intent.budget = None (remove ceiling)
   ├── style_change → intent.attributes["style"] = extracted_style(utterance)
   └── new_search   → route to IntentDiscoveryAgent fresh (return is_new_search: true)
3. Update StructuredIntent on the session document
4. Re-run vector_search_catalog with updated intent (same OG-013 path)
5. Apply match-quality threshold (same OG-014 path)
6. Generate grounded explanations (same OG-015 path, prompt references prior results for contrast)
7. Log search_refined event (resolution: "narrowed" | "new_search")
8. Check FitCheck trigger on new top result
9. Return SearchResponse with refinement_applied + updated_intent fields
```

**Anti-pattern explicitly prevented:** Refinement never re-calls Gemini for intent extraction when a Python pattern match is sufficient. This keeps p95 latency under 2s for refinement turns.

---

#### Intent + Discovery Agent — Voice/Multilingual Extension (OG-049)

**File:** No new file — extension of `backend/agents/discovery.py`

**Model:** `gemini-3.6-flash` (multimodal)

The existing `IntentDiscoveryAgent.run()` accepts an optional `audio_bytes: bytes | None` parameter. When present, the first Gemini call is replaced with a multimodal call that transcribes, detects language, and extracts intent in a single round-trip.

**Modified first step (when `audio_bytes` is provided):**
```python
VOICE_INTENT_PROMPT = """
You will receive an audio clip of a shopper search query.
1. Transcribe it exactly in the original language.
2. Detect the BCP-47 language code.
3. Extract structured intent as JSON: {category, attributes, budget, use_case, urgency}.
4. Do NOT translate to English. The category must still be one of our defined categories.

After this step, all result explanations must be generated in the same detected language.
"""

response = gemini_flash_multimodal.generate(
    contents=[audio_part, VOICE_INTENT_PROMPT],
    response_schema=VoiceIntentResponse  # {transcription, detected_language, intent}
)
```

From step 2 onward (embedding → vector search → threshold routing → explanations), the flow is identical to a text search. The only change: `generate_explanation()` receives `language=detected_language` and is instructed to respond in that language.

**Edge case handling:** If Gemini cannot reliably detect the language (confidence below threshold), the backend defaults to English and sets `detected_language: "und"` (undetermined) in the response — never crashes, never guesses and returns wrong-language output.

---

#### Fit-Check Agent — Follow-Up Extension (OG-050)

**File:** Inline extension of `backend/agents/fit_check.py`

**Trigger:** Called by `FitCheckAgent` immediately after logging a `fit_check` event whose resolution is `confirmed` or `size_changed`. Never called for `abandoned`.

**Model:** `gemini-3.6-flash`

```python
FOLLOW_UP_PROMPTS = {
    "size_changed": """
Write one short follow-up message (2 sentences max) for a shopper who just swapped from
{original_variant} to {new_variant} for SKU {sku_name}.
Acknowledge the smart choice using only these attributes: {sku_attributes}.
End with a brief easy-return reminder.
Do NOT invent facts about fit, feel, or performance not in the attributes.
""",
    "confirmed": """
Write one short follow-up message (2 sentences max) for a shopper who confirmed their
original size choice on {sku_name} despite a fit-check prompt.
Reference only these attributes: {sku_attributes}.
Include the store's return window as a confidence safety net.
Do NOT fabricate comfort claims or fit guarantees.
"""
}
```

The generated message is written to `follow_up_notifications` document (see §6.1) and the `delivered` flag starts as `False`. The Next.js frontend reads it via `GET /follow-up/{session_id}` at purchase confirmation time.

---

#### Insight Agent — Chat Mode (OG-051)

**File:** `backend/agents/insight_chat.py`

**Model:** `gemini-3.6-pro`

This is a separate class from the batch `InsightAgent` — it is stateful across turns (loads `MerchantChatSession` from Firestore) and uses a different system prompt and tool set.

**System prompt:** See §7.3 `POST /insights/chat` — the same prompt applies here.

**Tool set:** `CHAT_TOOLS` defined in §7.3.

**Execution flow:**
```
1. Load MerchantChatSession from Firestore (or create new if chat_session_id is None)
2. Append user turn to session.turns
3. Build Gemini request:
   ├── system_prompt: MERCHANT_CHAT_SYSTEM_PROMPT
   ├── tools: CHAT_TOOLS
   └── conversation_history: all prior turns (role: user/assistant)
4. Gemini Pro generates a response, optionally calling one or more tools
5. For each function_call in response:
   ├── Execute the Python query function against Firestore
   ├── Return results to Gemini as function_response
   └── Log to FunctionCallLog (name, arguments, result_summary)
6. Gemini synthesizes final answer from function results
7. Build ChatSource list from function results (cited values only)
8. Append assistant turn to session.turns (with sources + function_calls)
9. Save updated MerchantChatSession to Firestore
10. Return InsightChatResponse
```

**Unanswerable detection (Python post-processing):**
```python
def is_unanswerable(answer: str) -> bool:
    DECLINE_SIGNALS = ["I don't have", "cannot answer", "no data available", "outside my scope"]
    return any(sig.lower() in answer.lower() for sig in DECLINE_SIGNALS)
```

Sets `unanswerable: true` in the response when detected — this field lets the Next.js frontend render a distinct "I can't answer that" state rather than a normal answer card.

---

#### Catalog Import Agent

**File:** `backend/agents/catalog_import.py`

**Model:** `gemini-3.6-flash` (multimodal for PDF/image; text for Excel/CSV/URL)

**Runtime:** Cloud Run Job — not a service. Invoked by `POST /catalog/import`, runs to completion independently of the HTTP response.

This agent orchestrates a four-stage pipeline. Each stage updates `catalog_import_jobs.status` in Firestore so the admin can poll progress in real time.

---

**Stage 1 — Source Ingestion** *(Python, no LLM)*

Behavior varies by `input_type`. The output of all branches is the same: a list of `RawPage` objects, each containing raw text and image URLs extracted from one page or file section.

```python
class RawPage(BaseModel):
    source_url: str | None      # URL of the page (URL input only)
    depth: int                   # Crawl depth level (URL input only)
    raw_text: str                # All visible text from the page or document section
    image_urls: list[str]        # Product image URLs found on the page
    input_type: str
```

**Branch — URL:**
```
Crawler (httpx + BeautifulSoup):
  1. Fetch seed URL (depth 0)
  2. Extract all same-domain <a href> links
  3. Filter links:
     - Must be same domain as seed URL
     - Path must not match NON_PRODUCT_PATTERNS = ["/about", "/contact", "/blog", "/faq", "/policy"]
     - Must not have been visited already (dedup set)
  4. For each accepted link, fetch page content
  5. Repeat up to crawl_depth (default 3)
  6. Rate limit: 500ms delay between requests; respect robots.txt

Output: one RawPage per crawled URL
```

**Branch — PDF:**
```
1. Download from GCS (already uploaded by the API handler)
2. Split into pages (PyMuPDF or similar)
3. Each page → RawPage(raw_text=page_text, image_urls=[embedded_image_gcs_paths])
   Embedded images are extracted and uploaded to GCS for later Gemini multimodal access
```

**Branch — Image (JPEG/PNG):**
```
1. Download from GCS
2. Single RawPage with raw_text="" and image_urls=[gcs_path]
   (All extraction happens in Stage 2 via Gemini Vision)
```

**Branch — Excel / CSV:**
```
1. Download from GCS
2. Parse with pandas → DataFrame
3. Send column headers + first 5 rows to Gemini Flash:
   COLUMN_MAPPING_PROMPT:
   "Map these columns to SKU fields: name, category, price, stock, attributes, image_url.
    Return a JSON mapping {source_column: sku_field | null}.
    Only map columns that clearly correspond to a SKU field."
4. Apply mapping to all rows → list of raw_product dicts
5. Each dict → RawPage(raw_text=json.dumps(raw_product), image_urls=[])
```

---

**Stage 2 — Entity Extraction** *(Gemini Flash)*

One Gemini call per `RawPage`. Extracts all product-like entities found in the page content.

```python
EXTRACTION_PROMPT = """
You are a product catalog extractor. Read the page content and extract every distinct product you can identify.

For each product output a JSON object with these fields:
  name (string, required), description (string), price (number), currency (string),
  category_hint (string), attributes (object of key-value pairs),
  image_url (string), stock_hint (number or null)

RULES:
1. Only extract products explicitly mentioned in the page content.
2. If a field is not present in the source, leave it null — do not infer or guess.
3. If the page contains no products (e.g. it is a blog post or a contact page), return an empty array.
4. Do not combine data from multiple products into one entry.

Output: JSON array of product objects.
"""
```

For image-only `RawPage` objects, the call is multimodal — the image is passed alongside the prompt.

Results are aggregated across all pages into a flat `list[RawProductEntity]` and the progress counter `raw_entities_found` is updated.

---

**Stage 3 — Normalization to SKU Schema** *(Gemini Flash + Python validation)*

Each `RawProductEntity` is converted to a `SKUCandidate`. The LLM maps fuzzy field values to the platform's controlled vocabulary; Python validates the result.

```python
NORMALIZATION_PROMPT = """
Convert this raw product data to our SKU schema. Use ONLY information present in the raw data.

Platform categories (use exactly one): footwear | apparel | home_goods | electronics | accessories | other
Currency (use exactly one): INR | USD | GBP | EUR

Output a single JSON object:
  sku_id: generate a unique slug from the name (e.g. "heritage-canvas-tote")
  name, description, category, price (float), currency, stock (int, default 0 if unknown),
  return_rate (float, default by category: footwear=0.22, apparel=0.18, electronics=0.12, other=0.05),
  attributes (object), image_url (string or null)

RULES:
1. Do not invent a price if none is in the raw data — set price to null and the validator will reject it.
2. return_rate must use the category default shown above unless a specific rate is in the raw data.
3. Do not merge attributes from multiple products.
"""
```

**Python validation after normalization:**
```python
REQUIRED_FIELDS = ["name", "category", "price", "currency"]

def validate_candidate(candidate: dict) -> tuple[bool, str | None]:
    for field in REQUIRED_FIELDS:
        if not candidate.get(field):
            return False, f"{field}_missing"
    if candidate["category"] not in VALID_CATEGORIES:
        return False, "invalid_category"
    if not isinstance(candidate["price"], (int, float)) or candidate["price"] <= 0:
        return False, "invalid_price"
    return True, None
```

Invalid candidates are recorded in `error_details` and excluded from downstream stages — the job does not fail, it continues with valid candidates only.

**Deduplication (Python — no LLM):**
```python
# Exact name match against existing catalog (case-insensitive)
existing_names = {s.name.lower() for s in await firestore.get_all_sku_names(store_id)}
for candidate in valid_candidates:
    if candidate.name.lower() in existing_names:
        candidate.is_duplicate = True
        progress.skus_deduplicated += 1
```

**`confidence` score (Python formula, never LLM):**
```python
FIELD_WEIGHTS = {"name": 0.3, "price": 0.25, "category": 0.2, "image_url": 0.15, "description": 0.1}

def compute_confidence(candidate: dict) -> float:
    return sum(
        weight for field, weight in FIELD_WEIGHTS.items()
        if candidate.get(field) is not None
    )
```

---

**Stage 4 — Embedding + Catalog Write** *(Python + Vertex AI)*

Only runs when `dry_run=False` (or after `POST /catalog/import/{job_id}/confirm` on a dry-run job).

```python
async def embed_and_write(candidates: list[SKUCandidate], store_id: str):
    # Batch embedding — 100 SKUs per API call to stay within rate limits
    for batch in chunked(candidates, 100):
        texts = [f"{c.name}. {c.description}. {' '.join(f'{k}: {v}' for k,v in c.attributes.items())}" for c in batch]
        embeddings = await vertex_embeddings.embed_batch(texts, model="gemini-embedding-2")
        for candidate, embedding in zip(batch, embeddings):
            sku = SKU(
                sku_id=candidate.sku_id,
                embedding=embedding,
                **candidate.model_dump(exclude={"sku_id", "is_duplicate", "confidence"})
            )
            await firestore.upsert_sku(sku)
            progress.skus_added += 1
            progress.embeddings_generated += 1
        await asyncio.sleep(0.1)   # Respect Vertex AI quota
```

After writing, a JSON report is uploaded to `imports/{store_id}/{job_id}/report.json` in Cloud Storage and the job status is set to `"done"`.

---

## 9. System Flows (Backend)

### 9.1 Search Request Flow

```
Client (Next.js / Widget)
  │
  │  POST /search
  │  {query_text, session_id, store_id, platform}
  │  Bearer: <Firebase JWT>
  ▼
FastAPI — verify_token() → role_guard("shopper")
  │
  ├── If session_id is None: create new Session document in Firestore
  ├── If session_id provided: load existing Session
  │
  ▼
Orchestrator.route(event_type="search")
  │
  ▼
IntentDiscoveryAgent.run(query, session)
  │
  ├── 1. Gemini Flash call: extract_structured_intent (function-calling)
  │       → StructuredIntent {category, attributes, budget, ...}
  │
  ├── 2. Vertex AI Embeddings: embed(intent.to_text())
  │       → query_vector: list[float] (768-dim)
  │
  ├── 3. Firestore vector_search(query_vector, filters)
  │       → List[SKU] top-5, with scores
  │
  ├── 4. Score threshold routing:
  │       ≥ 0.75 → exact match path
  │       0.4–0.75 → near-match path (generate gap explanation)
  │       < 0.4 → miss path (broadest fallback + honest miss message)
  │
  ├── 5. Gemini Flash: generate grounded explanation per result
  │       (prompt restricts to retrieved SKU attributes only)
  │
  ├── 6. Write Event to Firestore (fire-and-forget, async)
  │       → Eventarc trigger → BigQuery append
  │
  ├── 7. FitCheck trigger check (Python):
  │       should_trigger(top_result_sku) → bool
  │       If true: FitCheckAgent.generate_question(sku) → question_text
  │
  └── 8. Return SearchResponse to FastAPI → HTTP 200 to client
```

---

### 9.2 Insight Generation Flow

```
Merchant clicks "Generate Insights" in Next.js dashboard
  │
  │  POST /insights/generate
  │  {store_id, time_window_days: 7}
  │  Bearer: <merchant JWT>
  ▼
FastAPI — verify_token() → role_guard("merchant") → verify store_id matches claims
  │
  ▼
InsightAgent.run(store_id, time_window_days)
  │
  ├── 1. Firestore query: events where store_id=X AND created_at > now-7d
  │       → raw_events: list[Event]
  │
  ├── 2. If len(raw_events) < MIN_EVENTS (5): return {"insights": [], "reason": "insufficient_data"}
  │
  ├── 3. Gemini Pro call: semantic clustering
  │       Input: list of query_text strings
  │       Output: [{label, query_indices}]
  │
  ├── 4. Python scoring loop (per cluster):
  │       - occurrences, unique_shoppers, trend_pct, est_revenue_at_risk, urgency_days
  │
  ├── 5. Python filtering: drop clusters where unique_shoppers < MIN_SHOPPERS (3)
  │
  ├── 6. Python signal classification per cluster
  │
  ├── 7. Gemini Pro call per cluster: generate_brief
  │       Input: scored + classified cluster dict
  │       Output: plain-language brief string
  │
  ├── 8. Write Insight documents to Firestore (one per cluster)
  │       → Next.js dashboard Firestore onSnapshot fires → UI updates live
  │
  └── 9. Return InsightResponse to FastAPI → HTTP 200 to client
```

---

### 9.3 Return Assessment Flow

```
Store Associate (Next.js PWA)
  │
  │  POST /return (multipart: image + order_id + store_id)
  │  Bearer: <associate JWT>
  ▼
FastAPI — verify_token() → role_guard("associate")
  │
  ├── Upload image to Cloud Storage: returns/store_001/{assessment_id}.jpg
  │
  ▼
ReturnIntelligenceAgent.run(image_gcs_path, order_id)
  │
  ├── STAGE 1 — Photo grading (Gemini Flash Vision):
  │       Input: image bytes + CONDITION_PROMPT
  │       Output: {condition: "lightly_used", justification: "..."}
  │       ⚠ NO fraud claims permitted in this stage
  │
  ├── STAGE 2 — Risk scoring (Python only):
  │       Fetch order history from Firestore for order_id
  │       compute_return_risk(order_history)
  │       → {tier: "high", factors: ["bracketing", "rapid_return"]}
  │
  ├── Disposition lookup (Python dict, NOT LLM):
  │       → "hold_for_review"
  │
  ├── Write ReturnAssessment to Firestore (disposition_confirmed=False)
  │
  └── Return ReturnAssessmentResponse → HTTP 200

Associate reviews in PWA — clicks "Confirm" or "Override"
  │
  │  POST /return/{assessment_id}/confirm
  │  {confirmed_disposition: "hold_for_review"}
  ▼
FastAPI — update ReturnAssessment: disposition_confirmed=True, confirmed_at=now()
  │
  └── Write Event(type=RETURN_CONFIRMED, resolution="hold_for_review")
```

---

### 9.4 Catalog Import Flow

```
Admin (Next.js dashboard)
  │
  │  POST /catalog/import
  │  {input_type: "url", url: "...", crawl_depth: 3, store_id: "...", dry_run: false}
  │  Bearer: <admin JWT>
  ▼
FastAPI — verify_token() → role_guard("admin")
  │
  ├── [URL input] HEAD request to validate URL is reachable → HTTP 400 if not
  ├── [File input] Upload file to GCS: imports/{store_id}/{job_id}/source.<ext>
  │
  ├── Create catalog_import_jobs document:
  │     status: "pending", progress: all zeros, input_source: url/gcs_path
  │
  ├── Invoke Cloud Run Job offgrid-catalog-import --job-id <job_id> (async)
  │
  └── HTTP 202 → {job_id, status: "pending", message: "Poll GET /catalog/import/{job_id}"}

━━━━━━━━━━━ Cloud Run Job runs independently ━━━━━━━━━━━

STAGE 1 — Source Ingestion
  │
  ├── [URL branch]
  │   ├── Update status: "uploading" (crawling)
  │   ├── Fetch seed URL → extract links (httpx + BeautifulSoup)
  │   ├── Filter: same domain only, skip NON_PRODUCT_PATTERNS
  │   ├── BFS up to crawl_depth=3 with 500ms rate-limit delay
  │   ├── Respect robots.txt — skip disallowed paths
  │   └── Output: list[RawPage], one per crawled URL
  │   
  ├── [PDF branch]
  │   ├── Download from GCS
  │   ├── Split pages via PyMuPDF
  │   ├── Extract embedded images → upload each to GCS
  │   └── Output: list[RawPage], one per PDF page
  │   
  ├── [Image branch]
  │   └── Output: single RawPage(raw_text="", image_urls=[gcs_path])
  │
  └── [Excel/CSV branch]
      ├── Parse with pandas → DataFrame
      ├── Gemini Flash: map source columns → SKU fields
      ├── Apply mapping → list of raw_product dicts
      └── Output: list[RawPage], one per row

STAGE 2 — Entity Extraction (Gemini Flash — one call per RawPage)
  │
  ├── Update status: "extracting"
  ├── For each RawPage:
  │   ├── [has image_urls] Gemini Flash multimodal call → list[RawProductEntity]
  │   └── [text only]      Gemini Flash text call       → list[RawProductEntity]
  ├── Aggregate all entities into flat list
  ├── Update progress.raw_entities_found
  └── Skip pages where Gemini returns [] (blog, contact, navigation pages)

STAGE 3 — Normalization + Validation + Deduplication (Gemini Flash + Python)
  │
  ├── Update status: "normalizing"
  ├── For each RawProductEntity:
  │   ├── Gemini Flash: convert to SKUCandidate (controlled-vocab category, return_rate default)
  │   ├── Python validate_candidate():
  │   │   ├── PASS → compute_confidence() → mark valid
  │   │   └── FAIL → record in error_details, skip
  │   └── Python dedup check: name.lower() in existing catalog names → mark duplicate
  │
  ├── Update progress.skus_normalized, skus_invalid, skus_deduplicated
  │
  └── [dry_run=True] → update status: "done", stop here
                        Admin may call GET /preview then POST /confirm

STAGE 4 — Embedding + Catalog Write (only if dry_run=False or after /confirm)
  │
  ├── Update status: "embedding"
  ├── Batch Vertex AI gemini-embedding-2 calls (100 SKUs per batch)
  │   ├── Input text: "{name}. {description}. {attributes as k:v string}"
  │   ├── Output: 768-dim float vector per SKU
  │   └── 100ms sleep between batches (Vertex AI quota)
  │
  ├── Update status: "writing"
  ├── Firestore upsert each SKU document (catalog collection)
  │   └── Update progress.skus_added, embeddings_generated after each batch
  │
  ├── Upload JSON report to GCS: imports/{store_id}/{job_id}/report.json
  │   └── Contains: full error_details list, all added sku_ids, timing stats
  │
  └── Update status: "done", completed_at: now()

━━━━━━━━━━━ Admin polls for completion ━━━━━━━━━━━

Admin frontend
  │
  │  GET /catalog/import/{job_id}   (polling, or Firestore onSnapshot)
  ▼
  ├── status: "extracting" / "normalizing" / "embedding" → show progress bar
  ├── status: "done" → show result summary + sample_sku_ids
  └── status: "failed" → show error_message + link to GCS report
```

**Error handling across all stages:**
- Network failures during URL crawl → retry 3× with exponential backoff; mark individual pages as failed, continue with others
- Gemini rate limit → `tenacity` exponential backoff; log each retry; never abort the job
- Validation failure on individual entity → record in `error_details`, continue
- Unrecoverable failure (GCS permission denied, Firestore write error) → set `status: "failed"` with `error_message`

### 9.5 Event → BigQuery Mirror Flow

```
Firestore write: events/{event_id}
  │
  │  Eventarc trigger (Firestore document-created)
  ▼
Cloud Run job: bq_mirror_handler.py
  │
  ├── Parse Firestore event payload
  ├── Map to BigQuery row schema
  ├── stream_insert to offgrid_events.events table
  └── Log success/failure to Cloud Logging

(Fallback: nightly batch job reconciles any missed Eventarc deliveries via BigQuery MERGE)
```

---

## 10. Infrastructure Layout

### 10.1 Repository Structure (Backend)

```
backend/
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── main.py                        # FastAPI app factory
├── config.py                      # Pydantic Settings — reads from env / Secret Manager
├── dependencies.py                # FastAPI deps: verify_token, require_role, get_db
│
├── routers/
│   ├── search.py                  # POST /search, POST /search/refine, POST /search/voice
│   ├── fit_check.py               # POST /fit-check, GET /follow-up/{session_id}
│   ├── return_intel.py            # POST /return, POST /return/{id}/confirm
│   ├── insights.py                # GET /insights, POST /insights/generate, POST /insights/chat
│   └── catalog.py                 # POST /catalog/import, GET /catalog/import/{id},
│                                  # GET /catalog/import/{id}/preview,
│                                  # POST /catalog/import/{id}/confirm,
│                                  # POST /catalog/embed, GET /catalog/{sku_id}
│
├── agents/
│   ├── orchestrator.py
│   ├── discovery.py               # Intent + Discovery agent (text, image, voice — OG-012–018, OG-049)
│   ├── discovery_refinement.py    # Iterative refinement mode — OG-048
│   ├── fit_check.py               # Fit-Check + follow-up generation — OG-019–022, OG-050
│   ├── return_intel.py            # Return Intelligence — OG-037–039
│   ├── insight.py                 # Batch insight pipeline — OG-023–028, OG-052, OG-053
│   ├── insight_chat.py            # Ask-your-data merchant chat — OG-051
│   └── catalog_import.py          # Catalog import pipeline (URL/PDF/image/Excel/CSV)
│
├── models/
│   ├── session.py
│   ├── sku.py
│   ├── event.py
│   ├── insight.py
│   ├── return_assessment.py
│   ├── follow_up_notification.py  # OG-050
│   ├── merchant_chat_session.py   # OG-051
│   └── catalog_import_job.py      # Catalog import job + progress tracking
│
├── services/
│   ├── firestore.py               # Firestore client + typed CRUD helpers
│   ├── embeddings.py              # Vertex AI Embeddings wrapper
│   ├── storage.py                 # Cloud Storage upload/signed-URL
│   ├── bigquery.py                # BQ insert helpers
│   └── crawler.py                 # URL crawler (httpx + BeautifulSoup, depth-3, robots.txt)
│
├── scripts/
│   ├── seed_catalog.py            # OG-006: load SKUs to Firestore
│   ├── generate_embeddings.py     # OG-007: embed catalog
│   ├── bq_mirror_handler.py       # Eventarc handler for BQ mirror
│   └── catalog_import_runner.py   # Cloud Run Job entrypoint — reads job_id arg, runs pipeline
│
└── tests/
    ├── unit/
    │   ├── test_discovery.py
    │   ├── test_fit_check.py
    │   ├── test_insight_scoring.py   # All numeric assertions
    │   ├── test_return_intel.py
    │   ├── test_catalog_import_normalization.py  # Validation + confidence score assertions
    │   └── test_crawler.py           # Depth/filter/robots.txt logic (mocked HTTP)
    └── integration/
        ├── test_search_flow.py       # Hits real Firestore (test project)
        ├── test_insight_pipeline.py
        └── test_catalog_import_e2e.py  # Small seed URL + real Firestore import
```

### 10.2 Cloud Run Services

**Cloud Run Services** (long-running, HTTP):

| Service Name | Entry Point | CPU | Memory | Min Instances | Timeout |
|---|---|---|---|---|---|
| `offgrid-api` | `uvicorn main:app` | 1 | 1 GiB | 1 (keep warm) | 60s |
| `offgrid-agent` | orchestrator dispatch | 2 | 2 GiB | 0 (scale-to-zero ok) | 120s |
| `offgrid-bq-mirror` | `bq_mirror_handler.py` | 1 | 512 MiB | 0 | 30s |

**Cloud Run Jobs** (run-to-completion, async):

| Job Name | Entry Point | CPU | Memory | Max Retries | Max Runtime |
|---|---|---|---|---|---|
| `offgrid-catalog-import` | `catalog_import_runner.py` | 2 | 4 GiB | 1 | 30 min |

The catalog import job is invoked via `gcloud run jobs execute offgrid-catalog-import --args job_id=<id>` from within the API service. The 4 GiB memory ceiling covers large Excel files (pandas) and batched embedding payloads. 30-minute timeout covers a depth-3 crawl of a large merchant site (typically 50–200 pages).

### 10.3 Deployment Pipeline

```
Developer push to main branch
  │
  ├── GitHub Actions:
  │   ├── ruff lint
  │   ├── mypy type check
  │   ├── pytest unit tests
  │   └── On pass:
  │       docker build → push to Artifact Registry
  │       gcloud run deploy offgrid-api --image <digest>
  │       gcloud run deploy offgrid-agent --image <digest>
  │
  └── Deployment verification: curl /health → 200
```

### 10.4 Secret Management

All secrets stored in Secret Manager. Cloud Run service pulls at startup via:
```python
# config.py
from google.cloud import secretmanager

class Settings(BaseSettings):
    vertex_ai_project: str = Field(default_factory=lambda: _get_secret("vertex-ai-project"))
    firebase_credentials: dict = Field(default_factory=lambda: json.loads(_get_secret("firebase-sa-key")))
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

Secrets in Secret Manager:
- `firebase-sa-key` — Firebase Admin SDK service account JSON
- `vertex-ai-project` — GCP project ID
- `gcs-bucket-name` — Cloud Storage bucket
- `bigquery-dataset` — BQ dataset ID

---

## 11. Implementation Phases & Milestones

### Phase 0 — Infrastructure Foundation
**Duration: Day 1 morning | Owner: Backend Lead**

| Task | Ticket | Exit Criteria |
|---|---|---|
| GCP project + billing + APIs | OG-001 | `gcloud services list` shows Vertex, Cloud Run, Firestore |
| Firebase project init (same GCP project) | OG-002 | `firebase deploy --only hosting` succeeds |
| Firestore schema + seed documents | OG-003 | 4 collections with typed placeholder docs |
| FastAPI skeleton deployed to Cloud Run | OG-004 | `GET /health` → 200 from external machine |
| Vertex AI Gemini auth test | OG-005 | Both local AND Cloud Run containers call Gemini successfully |

**Phase 0 milestone:** Any agent can be written against a deployed, accessible backend without infrastructure risk.

---

### Phase 1 — Data Preparation
**Duration: Day 1 afternoon | Owner: Backend Lead**

| Task | Ticket | Exit Criteria |
|---|---|---|
| Seed 300–500 SKU catalog to Firestore | OG-006 | `category == "footwear"` query returns realistic results |
| Generate embeddings for all catalog SKUs | OG-007 | Similar SKUs score >0.85 cosine similarity |
| Generate 50 synthetic shopper queries | OG-008 | Human-tagged query set exists with expected match types |
| Assign return rates to all SKUs | OG-009 | 3–5 demo SKUs confirmed above 0.20 threshold |
| Build multi-store stock matrix | OG-010 | 2 SKUs deliberately at 0 stock at home store |
| Source 6 return-condition photos | OG-011 | Photos in Cloud Storage, each human-labeled |

**Phase 1 milestone:** Discovery has a real, grounded catalog to search. Fit-Check has reliable trigger candidates. Return Intel has test images.

---

### Phase 2 — Discovery Agent
**Duration: Day 2 | Owner: Agent Developer**

| Task | Ticket | Exit Criteria |
|---|---|---|
| Structured intent function-calling | OG-012 | 10 varied queries → correct StructuredIntent (manual check) |
| Vector search retrieval + price filter | OG-013 | 5 synthetic queries → plausible SKU results with scores |
| Match-quality threshold + near-match fallback | OG-014 | All 50 synthetic queries return non-empty response |
| Grounded match explanations | OG-015 | Zero invented attributes in 10-sample held-out check |
| Image-query handling | OG-016 | 5 test photos → correct intent + results |
| Search event logging | OG-017 | 10 queries → 10 Firestore event documents |
| Anti-hallucination test suite | OG-018 | 10 adversarial prompts pass; results table saved |

**Phase 2 milestone:** Zero-dead-end search is provably working and grounded. Logging is running.

---

### Phase 3 — Fit-Check + Insight Pipeline
**Duration: Day 3 | Owner: Agent Developer**

| Task | Ticket | Exit Criteria |
|---|---|---|
| Fit-check trigger logic | OG-019 | Demo SKUs trigger; low-rate SKUs don't |
| SKU-specific question generation | OG-020 | 3 SKUs → 3 visibly distinct questions |
| Shopper response handler + cart update | OG-021 | 5 test phrasings → correct resolution + cart state |
| Fit-check event logging | OG-022 | 5 fit-check events in Firestore with correct resolutions |
| Event aggregation | OG-023 | Query returns exact events from a scripted session |
| Semantic clustering | OG-024 | 3 same-intent queries → 1 cluster |
| Code-based scoring | OG-025 | Hand-computed values match code output exactly |
| Signal type classification | OG-026 | 3 manufactured test cases classified correctly |
| Grounded merchant brief | OG-027 | 5-sample check: zero number mismatches |
| On-demand insights endpoint | OG-028 | Demo session → briefs in < 10 seconds |

**Phase 3 milestone:** Closed loop is real. Failed customer intent becomes a traceable merchant brief.

---

### Phase 4 — Return Intelligence + Deployment
**Duration: Day 4 | Owner: Backend Lead**

| Task | Ticket | Exit Criteria |
|---|---|---|
| Return photo condition grading | OG-037 | 5/6 OG-011 test images classified correctly |
| Code-based return risk scoring | OG-038 | High-risk and low-risk manufactured cases scored correctly |
| Human-in-the-loop confirm endpoint | OG-039 | No disposition state change before associate confirms |
| Firebase Hosting + Cloud Run fully deployed | OG-032 | Full shopper + merchant walkthrough on live URLs |

**Phase 4 milestone (Go/No-Go Gate):** A teammate who has never seen the app opens the live URL cold and completes the full loop unassisted.

---

### Phase 5A — Feature Extensions *(only if Phase 4 is stable)*
**Duration: Day 5 | Owner: Agent Developer**

| Task | Ticket | Effort |
|---|---|---|
| Iterative refinement ("show me cheaper") | OG-048 | 3h |
| Multilingual + voice search | OG-049 | 4h |
| Post-purchase fit follow-up | OG-050 | 2h |
| Ask-your-data merchant chat | OG-051 | 5h |
| Pricing gap signal type | OG-052 | 2h |
| Restock-by-date urgency | OG-053 | 1.5h |

**Priority if time-limited: OG-051 (merchant chat) — highest demo impact.**

---

### Phase 5B — Catalog Import Onboarding *(only if Phase 5A is stable)*
**Duration: Day 5–6 | Owner: Backend Lead**

| Task | Deliverable | Exit Criteria |
|---|---|---|
| `catalog_import_jobs` Firestore collection + model | `models/catalog_import_job.py` | Typed document with all `ImportStatus` enum values |
| Cloud Run Job `offgrid-catalog-import` scaffold | `scripts/catalog_import_runner.py` | Job executes, reads `job_id` arg, updates Firestore status to `"done"` with empty result |
| URL crawler service | `services/crawler.py` | Depth-3 crawl of a test site; same-domain filter; robots.txt respected; returns `list[RawPage]` |
| PDF + image extraction stage | Stage 2 of `catalog_import.py` | All 6 OG-011 return photos + a 5-page test PDF return plausible entity lists |
| Excel/CSV column mapping | Stage 1 Excel branch | A 10-column product spreadsheet with non-standard headers maps to SKU fields correctly |
| Normalization + validation stage | Stage 3 of `catalog_import.py` | Valid entities produce `confidence ≥ 0.5`; invalid (missing price) recorded in `error_details` |
| Deduplication | Python name-match check | Re-importing the same product file adds 0 new SKUs |
| Embedding + write stage | Stage 4 of `catalog_import.py` | 50 test candidates written to Firestore catalog with correct `embedding` field |
| REST endpoints | `routers/catalog.py` | `POST /catalog/import` → job_id; `GET /catalog/import/{id}` → live status; `/preview` + `/confirm` work for dry-run flow |
| Unit tests | `test_catalog_import_normalization.py`, `test_crawler.py` | Confidence formula, validate_candidate, classify_signal coverage |

**Verification:** Import a real merchant URL (or a supplied product PDF) end-to-end on deployed infra. Confirm new SKUs appear in `GET /search` results within one minute of job completion.

### Phase 6 — Submission Assets
**Duration: Day 6 | Owner: Whole Team**

| Task | Ticket | Exit Criteria |
|---|---|---|
| Pitch deck (PDF) | OG-043 | Teammate reads cold and understands live vs. roadmap |
| 3-minute demo video | OG-044 | Final cut ≤ 3 min, recorded against live URLs |
| Architecture diagram (scope-labeled) | OG-045 | Live components visually distinct from planned |
| README + category statement | OG-046 | Teammate follows README to working local env |
| Full end-to-end deployment verification | OG-047 | Every live scenario tested on deployed URLs before submission |

---

## 12. Environment Strategy

| Environment | GCP Project | Firestore | Cloud Run | Purpose |
|---|---|---|---|---|
| **local-dev** | Personal GCP project | Emulator | Local uvicorn | Developer iteration |
| **staging** | `offgrid-staging` | Real Firestore | Cloud Run (staging revision) | Integration testing, demo rehearsal |
| **production** | `offgrid-prod` | Real Firestore | Cloud Run (prod traffic) | Hackathon submission URL |

**Environment config** via Pydantic Settings reading from:
1. Environment variables (Cloud Run injects these)
2. `.env` file (local dev only, gitignored)
3. Secret Manager (production secrets only)

```python
# config.py
class Settings(BaseSettings):
    env: str = "local"                          # "local" | "staging" | "production"
    gcp_project_id: str
    firestore_database: str = "(default)"
    vertex_ai_location: str = "us-central1"
    gcs_bucket: str
    bq_dataset: str
    cors_origins: list[str] = ["http://localhost:3000"]  # next.js dev server
    
    # Scoring constants (documented, not magic numbers)
    INDUSTRY_CVR: float = 0.04                  # 4% e-commerce industry avg
    INSIGHT_MIN_SHOPPERS: int = 3               # Min unique shoppers per cluster to surface
    FIT_CHECK_RETURN_RATE_THRESHOLD: float = 0.20
    VECTOR_MATCH_THRESHOLD_EXACT: float = 0.75
    VECTOR_MATCH_THRESHOLD_NEAR: float = 0.40
```

---

## 13. Non-Functional Requirements

| Requirement | Target | Mechanism |
|---|---|---|
| **API latency (search)** | p95 < 3s | Gemini Flash; Cloud Run min-instances=1 (no cold starts); Firestore-native vector search |
| **Insight generation** | < 10s for hackathon-scale | Synchronous pipeline; flag if slower before Phase 6 |
| **Availability** | Best-effort (hackathon) | Cloud Run managed; no custom SLO required |
| **Grounding** | Zero hallucinated facts | Anti-hallucination prompts; OG-018 adversarial suite; OG-027 held-out check |
| **Numeric accuracy** | All numbers code-computed | Audited by `test_insight_scoring.py`; any LLM arithmetic is a P0 bug |
| **Scalability** | Single-tenant demo | Architecture is multi-tenant ready (`store_id` scoping throughout) |
| **Security** | Firebase Auth on all endpoints | Server-side token verification; Secret Manager for credentials; CORS locked |
| **Observability** | Structured JSON logs | `structlog` → Cloud Logging; log every agent invocation + duration |

---

## 14. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Vertex AI rate limits during demo | Medium | High | `tenacity` exponential backoff on all Gemini calls; warm up pre-demo |
| Firestore vector search cold-start latency | Low | Medium | Pre-query at deploy time; keep min-instances=1 |
| CORS misconfiguration on Firebase → Cloud Run | High | High | Explicit CORS test in OG-032 against deployed URLs (not localhost) |
| LLM invents a number in Insight brief | Medium | High | Prompt forbids it; `test_insight_scoring.py` asserts all numbers are Python-computed before brief generation |
| ADK agent mesh adds debugging overhead | Medium | Medium | Phase 2–3 built against direct Gemini function-calling first; ADK introduced only after core loop is proven |
| Return Intelligence fraud claim slippage | Medium | High | CONDITION_PROMPT explicitly forbids fraud language; risk scoring is Python-only (never passes through LLM) |
| Phase 4 not stable before stretch work begins | Medium | High | Phase 4 exit criteria is a hard gate — stretch tickets never start until a teammate completes the cold walkthrough |
| Demo Firestore data drifts between rehearsal and submission | Low | Medium | OG-047 mandates a full end-to-end run on live URLs ≤ 4h before submission deadline |
| Catalog import: JS-rendered storefront pages not crawled by httpx | Medium | Medium | Playwright headless browser as a drop-in replacement for httpx on pages that return empty HTML — detect via response body length check post-fetch |
| Catalog import: LLM returns empty entity list for text-heavy pages | Medium | Low | Per-page extraction; empty arrays are expected and skipped; overall job continues — only a problem if the entire crawl yields zero entities |
| Catalog import: Vertex AI Embeddings quota exceeded on large catalog (500+ SKUs) | Low | Medium | Batch size of 100 + 100ms sleep between batches stays within default quota; raise limit in GCP console before a large import |
| Catalog import job exceeds 30-minute timeout on very large sites | Low | Medium | Crawl depth is capped at 3 and `MAX_PAGES_PER_JOB = 300` constant prevents runaway crawls; document limit in admin UI |

---

*Companion documents: `solution.md` (product brief), `architecture.md` (system diagram), `flow_diagram.md` (sequence diagrams), `feasible_plan_v2.md` (lean fallback), `ticket_specs.md` (per-ticket acceptance criteria)*

*Frontend implementation (Next.js) is out of scope for this document.*
