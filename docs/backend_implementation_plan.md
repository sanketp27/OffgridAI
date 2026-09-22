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
| LLM Provider | Vertex AI (Gemini) | Flash 2.0 for interactive agents; Pro 2.0 for batch Insight |
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
| `httpx` | Async HTTP client for inter-service calls if needed |

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
│  │  Gemini Embeddings (text-embedding-004)                       │  │
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
| Vertex AI | `us-central1` | Gemini Flash + Pro + text-embedding-004 |
| Secret Manager | Regional `us-central1` | API service account key, Vertex AI credentials |
| Artifact Registry | `us-central1` | Docker image store for Cloud Run deploys |
| Cloud Scheduler | — | Nightly insight batch (cron: `0 2 * * *`) |
| Eventarc | Firestore → BigQuery trigger | Mirror events collection writes automatically |

---

## 5. IAM & Identity Architecture

### 5.1 Service Accounts

| SA Name | Bound To | Roles Granted |
|---|---|---|
| `offgrid-api-sa` | Cloud Run API service | `roles/datastore.user`, `roles/storage.objectAdmin`, `roles/aiplatform.user`, `roles/secretmanager.secretAccessor` |
| `offgrid-agent-sa` | Cloud Run agent workers | `roles/datastore.user`, `roles/aiplatform.user`, `roles/storage.objectViewer` |
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
    embedding: list[float]    # Gemini text-embedding-004 vector (768-dim)
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
    FIT_CHECK = "fit_check"
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
| `fit_check` | `"confirmed"` \| `"size_changed"` \| `"variant_changed"` \| `"abandoned"` |
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
│       └── {sku_id}.jpg          # Product images (public-read)
├── returns/
│   └── {store_id}/
│       └── {assessment_id}.jpg   # Return photos (private; signed URL for associate access)
└── shelf/
    └── {store_id}/
        └── {timestamp}.jpg       # Shelf photos (future: planogram compliance)
```

---

## 7. API Contract

**Base URL:** `https://api.offgrid.ai` (Cloud Run managed domain)
**Auth:** `Authorization: Bearer <Firebase JWT>` on all endpoints except `/health`
**Content-Type:** `application/json` (except multipart endpoints)

---

### 7.1 Endpoint Inventory

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

## 8. Agent Architecture

### 8.1 Agent Mesh Overview

All agents are Python classes conforming to the Google ADK `Agent` interface. The Orchestrator is the sole entry point — it receives a normalized payload from the FastAPI layer and returns a unified response. Agents never call each other directly.

```
FastAPI Layer
    │
    ▼
Orchestrator Agent
    ├── Intent + Discovery Agent   (Gemini Flash, function-calling)
    ├── Fit-Check Agent            (Gemini Flash, function-calling)
    ├── Return Intelligence Agent  (Gemini Flash, multimodal)
    └── Insight Agent              (Gemini Pro, batch)
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
    "search":              [IntentDiscoveryAgent],
    "fit_check_response":  [FitCheckAgent],
    "return":              [ReturnIntelligenceAgent],
    "insights_generate":   [InsightAgent],
}
```

**System prompt:** None — the Orchestrator is pure Python routing logic. It does not call an LLM itself.

---

#### Intent + Discovery Agent

**File:** `backend/agents/discovery.py`

**Model:** `gemini-2.0-flash`

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

**Model:** `gemini-2.0-flash`

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

**Model:** `gemini-2.0-flash` (multimodal)

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

**Model:** `gemini-2.0-pro` (batch)

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

### 9.4 Event → BigQuery Mirror Flow

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
│   ├── search.py                  # POST /search
│   ├── fit_check.py               # POST /fit-check
│   ├── return_intel.py            # POST /return, POST /return/{id}/confirm
│   ├── insights.py                # GET /insights, POST /insights/generate
│   └── admin.py                   # POST /catalog/embed, etc.
│
├── agents/
│   ├── orchestrator.py
│   ├── discovery.py               # Intent + Discovery agent
│   ├── fit_check.py
│   ├── return_intel.py
│   └── insight.py
│
├── models/
│   ├── session.py
│   ├── sku.py
│   ├── event.py
│   ├── insight.py
│   └── return_assessment.py
│
├── services/
│   ├── firestore.py               # Firestore client + typed CRUD helpers
│   ├── embeddings.py              # Vertex AI Embeddings wrapper
│   ├── storage.py                 # Cloud Storage upload/signed-URL
│   └── bigquery.py                # BQ insert helpers
│
├── scripts/
│   ├── seed_catalog.py            # OG-006: load SKUs to Firestore
│   ├── generate_embeddings.py     # OG-007: embed catalog
│   └── bq_mirror_handler.py       # Eventarc handler for BQ mirror
│
└── tests/
    ├── unit/
    │   ├── test_discovery.py
    │   ├── test_fit_check.py
    │   ├── test_insight_scoring.py  # All numeric assertions
    │   └── test_return_intel.py
    └── integration/
        ├── test_search_flow.py      # Hits real Firestore (test project)
        └── test_insight_pipeline.py
```

### 10.2 Cloud Run Services

| Service Name | Entry Point | CPU | Memory | Min Instances | Timeout |
|---|---|---|---|---|---|
| `offgrid-api` | `uvicorn main:app` | 1 | 1 GiB | 1 (keep warm) | 60s |
| `offgrid-agent` | orchestrator dispatch | 2 | 2 GiB | 0 (scale-to-zero ok) | 120s |
| `offgrid-bq-mirror` | `bq_mirror_handler.py` | 1 | 512 MiB | 0 | 30s |

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

---

*Companion documents: `solution.md` (product brief), `architecture.md` (system diagram), `flow_diagram.md` (sequence diagrams), `feasible_plan_v2.md` (lean fallback), `ticket_specs.md` (per-ticket acceptance criteria)*

*Frontend implementation (Next.js) is out of scope for this document.*
