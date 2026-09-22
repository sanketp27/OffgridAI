# OffGrid AI — Flow Diagrams

Render with any Mermaid-compatible viewer (GitHub, GitLab, Obsidian, mermaid.live).

---

## 1. The Rescue Loop (Core Flywheel)

```mermaid

flowchart TD

    A([Customer Arrives]) --> B[Intent Agent\nparses input\ntext · image · voice]

    B --> C{Input type?}

    C -->|Text query| D[Normalize query\nhandle slang & synonyms]

    C -->|Image| E[Gemini Vision\nextract visual attributes]

    C -->|Voice| F[Transcribe + normalize]

    D & E & F --> G[Discovery + Rescue Agent\nVector search over catalog]

    G --> H{Match quality?}

    H -->|Score ≥ 0.75\nGood match| I[Return ranked results\nwith grounded reasons]

    H -->|Score < 0.75\nWeak match| J[Explain gap\n+ show near-matches]

    H -->|SKU out of stock| K[RESCUE MODE\nFind substitutes\nCheck local availability]

    I --> L{Category return-prone?}

    J --> M[Log: unmet_demand signal] --> L

    K --> N[Explain trade-off\nin plain language] --> O{Customer accepts\nsubstitute?}

    O -->|Yes| P[Swap cart item\nLog: substitute_accepted]

    O -->|No| Q[Log: rescue_declined\nShow alternatives]

    L -->|Yes + return_rate > 20%| R[Fit-Check Agent\nOne targeted question]

    L -->|No| S[Proceed to cart]

    R --> T{Shopper responds}

    T -->|Changes size/variant| U[Update cart\nLog: resolution_flip]

    T -->|Confirms selection| V[Log: confirmed]

    T -->|Ignores| W[Log: abandoned]

    U & V & W & S & P & Q --> X[(Firestore\nEvent Log)]

    X --> Y[(BigQuery\nMirror)]

    X --> Z[Insight Agent\nBatch / On-Demand]

    Z --> AA[Cluster events\nby meaning]

    AA --> AB[Score in code\nrevenue at risk · trend]

    AB --> AC[Generate merchant briefs\nGemini Pro — prose only]

    AC --> AD[Merchant Dashboard\nActionable signals]

    AD --> AE{Action type?}

    AE -->|Stock gap| AF[Source new SKU]

    AE -->|Discoverability gap| AG[Fix tags / synonyms]

    AE -->|Sizing confusion| AH[Fix size chart]

    AF & AG & AH --> AI([Better experience\nfor next customer])

    AI -.->|Loop restarts| A

    style A fill:#2196F3,color:#fff

    style AI fill:#4CAF50,color:#fff

    style K fill:#FF9800,color:#fff

    style R fill:#9C27B0,color:#fff

    style Z fill:#E91E63,color:#fff

    style AD fill:#009688,color:#fff

```

---

## 2. Scenario 1 — Smart Discovery Flow

```mermaid

flowchart LR

    S1([Shopper]) -->|Text or image query| A1[JS Embed Widget]

    A1 -->|POST /api/search| B1[Cloud Run API]

    B1 --> C1[Orchestrator]

    C1 --> D1[Intent Agent\nGemini Flash]

    D1 -->|Structured intent| C1

    C1 --> E1[Discovery Agent]

    E1 -->|Embedding| F1[(Vector Index\nFirestore)]

    F1 -->|Top-k SKUs| E1

    E1 -->|Match score ≥ 0.75?| G1{Decision}

    G1 -->|Yes| H1[Build result cards\nwith grounded reasons]

    G1 -->|No| I1[Explain gap\nnear-matches only]

    H1 & I1 -->|Log event| J1[(Firestore Events)]

    H1 --> K1[Fit-Check trigger check]

    K1 -->|Apparel SKU\nhigh return rate| L1[Fit-Check Agent\nOne targeted question]

    K1 -->|Other category| M1[Return results]

    L1 -->|Shopper answers| N1[Update cart or confirm]

    N1 -->|Log resolution| J1

    M1 & N1 --> O1([Confident purchase])

    style S1 fill:#2196F3,color:#fff

    style O1 fill:#4CAF50,color:#fff

    style L1 fill:#9C27B0,color:#fff

```

---

## 3. Scenario 2 — Stockout Rescue Flow

```mermaid

flowchart TD

    S2([Shopper requests\nspecific SKU]) --> A2[Discovery Agent\nchecks inventory]

    A2 --> B2{In stock?}

    B2 -->|Yes| C2[Normal result flow]

    B2 -->|No| D2[RESCUE MODE]

    D2 --> E2[find_substitutes\nsku_id + intent]

    D2 --> F2[check_local_availability\nsku_id + region]

    E2 --> G2[(Catalog\nFirestore)]

    F2 --> H2[(Inventory\nFirestore)]

    G2 -->|Substitute SKUs| I2[Rank substitutes\nby intent match]

    H2 -->|Nearby store stock| J2[Check fulfilment timing]

    I2 & J2 --> K2[Build rescue response\nExplain trade-offs in plain language]

    K2 -->|Grounded on real SKU data only| L2[Present options to shopper]

    L2 --> M2{Shopper decision}

    M2 -->|Accepts substitute| N2[Update cart\nLog: substitute_accepted]

    M2 -->|Declines| O2[Log: rescue_declined\nShow more alternatives]

    M2 -->|Abandons| P2[Log: stockout_lost\nunmet demand signal]

    N2 & O2 & P2 --> Q2[(Firestore Events\n→ BigQuery)]

    style S2 fill:#2196F3,color:#fff

    style D2 fill:#FF9800,color:#fff

    style N2 fill:#4CAF50,color:#fff

    style P2 fill:#f44336,color:#fff

```

---

## 4. Scenario 3 — Return-to-Value Flow

```mermaid

flowchart TD

    S3([Store Associate\nuploads return photo]) --> A3[Associate PWA]

    A3 -->|POST /api/return\nimage + order_id| B3[Cloud Run API]

    B3 --> C3[Return Intelligence Agent\nGemini Flash Vision]

    C3 --> D3[Analyze image]

    D3 --> E3{Condition?}

    E3 -->|New / tags intact| F3[condition: new]

    E3 -->|Light wear| G3[condition: lightly_used]

    E3 -->|Damaged| H3[condition: damaged]

    E3 -->|Suspected counterfeit| I3[condition: counterfeit_suspected]

    C3 --> J3[Check order history\nFirestore]

    J3 --> K3{Product matches\norder?}

    K3 -->|No| L3[Flag: identity_mismatch]

    K3 -->|Yes| M3[Check fraud signals]

    M3 --> N3{Fraud indicators?}

    N3 -->|Yes| O3[Flag: fraud_suspected]

    N3 -->|No| P3[Clean return]

    F3 & G3 & H3 & I3 --> Q3[Disposition Logic\nCode — not LLM]

    L3 & O3 --> Q3

    P3 --> Q3

    Q3 --> R3{Disposition}

    R3 -->|new + clean| S3[RESTOCK\nFull value recovered]

    R3 -->|lightly_used + clean| T3[REFURBISH\nRelist at 15% discount]

    R3 -->|damaged| U3[LIQUIDATE\n40% markdown]

    R3 -->|fraud flagged| V3[HOLD FOR REVIEW\nAlert manager]

    S3 & T3 & U3 & V3 --> W3[Write disposition\nto Firestore]

    W3 --> X3[Merchant Dashboard\nUpdates recovered value]

    W3 --> Y3[(BigQuery\nReturn analytics)]

    style S3_node fill:#4CAF50,color:#fff

    style V3 fill:#f44336,color:#fff

    style S3 fill:#4CAF50,color:#fff

    style Q3 fill:#FF9800,color:#fff

```

---

## 5. Insight Agent Pipeline Flow

```mermaid

flowchart LR

    A4[Trigger\nOn-demand button\nor nightly schedule] --> B4[aggregate_events\ntime_window: 7d]

    B4 --> C4[(Firestore\nEvents)]

    C4 -->|Raw events| B4

    B4 --> D4[Gemini Pro\nCluster by meaning\nnot exact string]

    D4 --> E4[Clusters\nlabeled by intent]

    E4 --> F4[Score in CODE\nnever LLM]

    F4 --> G4{For each cluster}

    G4 --> H4[occurrences = count]

    G4 --> I4[unique_shoppers = distinct sessions]

    G4 --> J4[trend_pct = delta vs prior window]

    G4 --> K4[revenue_at_risk = occurrences × CVR × AOV]

    H4 & I4 & J4 & K4 --> L4[Filter noise\nunique_shoppers ≥ MIN]

    L4 --> M4[Classify signal type]

    M4 --> N4{Type?}

    N4 -->|Item not in catalog| O4[Stock gap\nRecommend: source SKU]

    N4 -->|Item exists, not found| P4[Discoverability gap\nRecommend: fix tags]

    N4 -->|High fit-check flip rate| Q4[Sizing confusion\nRecommend: fix size chart]

    O4 & P4 & Q4 --> R4[generate_brief\nGemini Pro\nProse grounded on step scores only]

    R4 --> S4[(Firestore\nInsights)]

    S4 --> T4[Merchant Dashboard\nCards with revenue-at-risk badges]

    style A4 fill:#E91E63,color:#fff

    style F4 fill:#FF9800,color:#fff

    style T4 fill:#009688,color:#fff

```

---

## 6. Cross-Platform Integration Flow

```mermaid

flowchart TB

    subgraph PLATFORMS["Any Commerce Platform"]

        SH["Shopify\n<script> embed"]

        WC["WooCommerce\n<script> embed"]

        CU["Custom Site\n<script> embed"]

        POS["Physical POS\nREST API call"]

        WA["WhatsApp / SMS\nWebhook → REST"]

        MOB["Mobile App\nFirebase SDK"]

    end

    subgraph ENTRY["Universal Entry Point"]

        API["Cloud Run REST API\nPlatform-agnostic event schema"]

    end

    subgraph AGENTS["Agent Mesh (ADK)"]

        direction TB

        O["Orchestrator"]

        A1["Intent"]

        A2["Discovery\n+ Rescue"]

        A3["Fit-Check"]

        A4["Return\nIntelligence"]

        A5["Insight"]

        O --> A1 & A2 & A3 & A4 & A5

    end

    subgraph OUTPUTS["Outputs (Any Consumer)"]

        W1["Shopper Widget\nresults + fit-check"]

        W2["Associate PWA\ndisposition card"]

        W3["Merchant Dashboard\ninsight briefs"]

        W4["BigQuery\nExternal BI / Looker"]

        W5["Webhook response\nWhatsApp reply"]

    end

    SH & WC & CU & POS & WA & MOB --> API

    API --> O

    A1 & A2 & A3 & A4 & A5 --> W1

    A4 --> W2

    A5 --> W3

    A5 --> W4

    A2 --> W5

    style PLATFORMS fill:#e8f4fd,stroke:#2196F3

    style ENTRY fill:#fff3e0,stroke:#FF9800

    style AGENTS fill:#f3e5f5,stroke:#9C27B0

    style OUTPUTS fill:#e8f5e9,stroke:#4CAF50

```

---

## Event Schema (Shared Across All Flows)

```mermaid

erDiagram

    SESSION {

        string session_id PK

        string platform

        timestamp created_at

        json cart

    }

    EVENT {

        string event_id PK

        string session_id FK

        string platform

        enum type

        string sku_id FK

        boolean matched

        float score

        string resolution

        float revenue_at_risk

        timestamp created_at

    }

    SKU {

        string sku_id PK

        string name

        string category

        float price

        int stock

        float return_rate

        float[] embedding

        json store_availability

    }

    INSIGHT {

        string insight_id PK

        enum signal_type

        string label

        int occurrences

        int unique_shoppers

        float trend_pct

        float revenue_at_risk

        string brief

        timestamp generated_at

    }

    SESSION ||--o{ EVENT : "generates"

    SKU ||--o{ EVENT : "referenced_by"

    EVENT }o--|| INSIGHT : "aggregated_into"

```
