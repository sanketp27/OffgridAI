# OffGrid AI — Architecture Diagram

Render with any Mermaid-compatible viewer (GitHub, GitLab, Obsidian, mermaid.live).

---

## System Architecture

```mermaid
graph TB
    subgraph CUSTOMER_SURFACES["Customer Surfaces (Any Platform)"]
        WEB["Web Storefront<br/>JS Embed Snippet"]
        MOB["Mobile App<br/>Firebase SDK"]
        MSG["Messaging<br/>WhatsApp / Telegram<br/>(stretch)"]
    end

    subgraph ASSOCIATE_MERCHANT["Business Surfaces"]
        ASC["Store Associate PWA<br/>Firebase Hosting"]
        MER["Merchant Dashboard<br/>Firebase Hosting"]
    end

    subgraph API_LAYER["REST API — Cloud Run"]
        API["FastAPI Gateway<br/>/search  /fit-check<br/>/return  /insights"]
    end

    subgraph AGENT_MESH["Agent Mesh — Google ADK (Cloud Run)"]
        ORC["Orchestrator Agent<br/>Routes events to specialists"]
        INT["Intent Agent<br/>text / image / voice → structured intent<br/>Gemini Flash"]
        DIS["Discovery + Rescue Agent<br/>Vector search · Substitutes · Stockout rescue<br/>Gemini Flash"]
        FIT["Fit-Check Agent<br/>Return-prone SKU clarifier<br/>Gemini Flash"]
        RET["Return Intelligence Agent<br/>Multimodal condition · Fraud · Disposition<br/>Gemini Flash"]
        INS["Insight Agent<br/>Cluster · Score · Brief<br/>Gemini Pro (batch)"]
    end

    subgraph DATA_LAYER["Data Layer"]
        FS["Firestore<br/>Sessions · Catalog<br/>Events · Insights"]
        VS["Vector Index<br/>Firestore Vector Search<br/>(Vertex AI Vector Search — stretch)"]
        GCS["Cloud Storage<br/>Product images<br/>Return / shelf photos"]
        BQ["BigQuery<br/>Event log<br/>SQL-queryable by any BI tool"]
    end

    subgraph GOOGLE_AI["Google AI (Vertex AI)"]
        GMF["Gemini Flash<br/>Interactive turns<br/>Multimodal"]
        GMP["Gemini Pro<br/>Batch insight synthesis"]
        EMB["Gemini Embeddings<br/>Catalog + query vectors"]
    end

    %% Surface → API
    WEB -->|"POST /api/search<br/>POST /api/fit-check"| API
    MOB -->|"REST"| API
    MSG -->|"Webhook → REST"| API
    ASC -->|"POST /api/return"| API
    MER -->|"GET /api/insights<br/>POST /api/insights/generate"| API

    %% API → Orchestrator
    API --> ORC

    %% Orchestrator → Specialists
    ORC --> INT
    ORC --> DIS
    ORC --> FIT
    ORC --> RET
    ORC -->|"on-demand / scheduled"| INS

    %% Agents → AI
    INT --> GMF
    DIS --> GMF
    FIT --> GMF
    RET --> GMF
    INS --> GMP

    %% Agents → Data
    DIS --> VS
    DIS --> FS
    FIT --> FS
    RET --> GCS
    RET --> FS
    INS --> FS
    INS --> BQ

    %% Embeddings
    EMB --> VS

    %% Firestore → BigQuery mirror
    FS -->|"Eventarc trigger"| BQ

    %% Merchant reads insights
    MER -->|"onSnapshot listener"| FS

    style CUSTOMER_SURFACES fill:#e8f4fd,stroke:#2196F3
    style ASSOCIATE_MERCHANT fill:#e8f5e9,stroke:#4CAF50
    style API_LAYER fill:#fff3e0,stroke:#FF9800
    style AGENT_MESH fill:#f3e5f5,stroke:#9C27B0
    style DATA_LAYER fill:#fce4ec,stroke:#E91E63
    style GOOGLE_AI fill:#e0f2f1,stroke:#009688
```

---

## Component Descriptions

### Customer Surfaces
- **JS Embed Snippet** (`embed/omnirerescue.js`): A single `<script>` tag that injects the OffGrid widget into any web storefront. No framework dependency. Sends events to the Cloud Run REST API.
- **Mobile (Firebase SDK)**: iOS/Android apps integrate via Firebase for real-time session sync and push notifications.
- **Messaging (stretch)**: WhatsApp/Telegram bots forward messages as webhook POST requests to the same REST API — no agent code changes required.

### Business Surfaces
- **Store Associate PWA**: Progressive Web App served from Firebase Hosting. Works on any browser/device. Handles shelf photo upload and return item analysis.
- **Merchant Dashboard**: Real-time updates via Firestore `onSnapshot`. Shows insight cards, event log, and revenue-at-risk metrics.

### REST API (Cloud Run)
FastAPI application. Stateless — all state lives in Firestore. Horizontal scaling handled by Cloud Run automatically.

### Agent Mesh (Google ADK)
- **Orchestrator**: Receives the normalized API payload, determines which specialist agent(s) to invoke, maintains session continuity.
- **Specialists**: Each agent has a focused system prompt, a fixed tool list, and an anti-hallucination guardrail. Agents never call each other directly — only through the Orchestrator.

### Data Layer
- **Firestore**: Primary operational store. Source of truth for sessions, catalog, events, and insights.
- **Vector Index**: Stores Gemini embeddings per SKU for semantic search. Firestore-native for MVP; Vertex AI Vector Search for production scale.
- **Cloud Storage**: Immutable image store for catalog photos, return item photos, and shelf images.
- **BigQuery**: Append-only event mirror. Enables SQL analysis and integration with any external BI tool (Looker, Data Studio, Tableau).

---

## Data Flow (Numbered Sequence)

```mermaid
sequenceDiagram
    actor Shopper
    participant Widget as JS Widget
    participant API as Cloud Run API
    participant Orch as Orchestrator
    participant Intent as Intent Agent
    participant Disc as Discovery Agent
    participant Fit as Fit-Check Agent
    participant FS as Firestore
    participant BQ as BigQuery

    Shopper->>Widget: "Show me something like this" + photo
    Widget->>API: POST /api/search {image_base64, session_id}
    API->>Orch: route(event)
    Orch->>Intent: parse(image_bytes)
    Intent-->>Orch: {category:"home_goods", attributes:{style:"rattan"}}
    Orch->>Disc: search(intent)
    Disc->>FS: vector_search(embedding, filters)
    FS-->>Disc: [SKU-042, SKU-107, SKU-203]
    Disc-->>Orch: ranked results + match explanations
    Orch->>FS: log_event(type="search", matched=true, score=0.87)
    FS->>BQ: mirror event (Eventarc)
    Orch-->>API: results payload
    API-->>Widget: JSON response
    Widget-->>Shopper: 3 product cards with reasons

    Note over Shopper,Fit: Shopper adds apparel SKU to cart

    Orch->>Fit: should_trigger?(sku_id, category)
    Fit-->>Orch: true (return_rate=0.28)
    Orch->>Fit: generate_question(sku_id)
    Fit-->>Widget: "This runs half a size small — do you usually size up?"
    Shopper-->>Widget: "I'll go with 9.5"
    Fit->>FS: log_event(type="fit_check", resolution="size_changed")
```

