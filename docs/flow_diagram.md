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

    R3 -->|new + clean| S3_disp[RESTOCK\nFull value recovered]

    R3 -->|lightly_used + clean| T3[REFURBISH\nRelist at 15% discount]

    R3 -->|damaged| U3[LIQUIDATE\n40% markdown]

    R3 -->|fraud flagged| V3[HOLD FOR REVIEW\nAlert manager]

    S3_disp & T3 & U3 & V3 --> W3[Write disposition\nto Firestore]

    W3 --> X3[Merchant Dashboard\nUpdates recovered value]

    W3 --> Y3[(BigQuery\nReturn analytics)]

    style S3 fill:#2196F3,color:#fff
    style S3_disp fill:#4CAF50,color:#fff
    style V3 fill:#f44336,color:#fff
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

## 7. Mesh Architecture Extension & Gaps Plugged

```mermaid
flowchart TB
    subgraph EXISTING["Existing Agents"]
        DIS["Discovery + Rescue Agent"]
        FIT["Fit-Check Agent"]
        RET["Return Intelligence Agent"]
        INS["Insight Agent"]
        CAT["Catalog Import Agent"]
    end

    subgraph GAP1["Conversational Shopping - extends Discovery"]
        CS1["Guided Narrowing"]
        CS2["Use-Case Bundle Search"]
        CS3["Cart Concierge"]
        CS4["Visual + Voice Continuity"]
    end

    subgraph GAP2["Demand Planning - NEW agent"]
        DP0["Demand Planning Agent\nGemini Pro + BigQuery ML"]
        DP1["Forecast Bridge"]
        DP2["Auto-Reorder Draft"]
        DP3["Price Simulator"]
        DP4["Seasonal Brief"]
    end

    subgraph GAP3["Fraud - NEW agent"]
        FR0["Fraud Scoring Agent\nGemini Flash + Python rules"]
        FR1["Checkout Risk Score"]
        FR2["Return-Abuse Mining"]
        FR3["Promo Stacking Detector"]
        FR4["Counterfeit Screen"]
    end

    subgraph GAP4["Insights - extends Insight Agent"]
        IN1["Cross-Sell Signal"]
        IN2["Cohort Briefs"]
        IN3["Competitive Price-Gap"]
        IN4["Trend Drilldown"]
        IN5["Weekly Digest"]
    end

    DIS --> CS1
    DIS --> CS2
    DIS --> CS3
    DIS --> CS4
    INS --> DP0
    DP0 --> DP1
    DP1 --> DP2
    DP1 --> DP3
    DP1 --> DP4
    DIS -.->|"checkout_start event"| FR0
    FR0 --> FR1
    INS --> FR2
    FR0 --> FR3
    CAT --> FR4
    INS --> IN1
    INS --> IN2
    INS --> IN3
    INS --> IN4
    INS --> IN5
    CAT -.->|"competitor crawl reused"| IN3

    style GAP1 fill:#e8f4fd,stroke:#2196F3
    style GAP2 fill:#fce4ec,stroke:#E91E63
    style GAP3 fill:#fce4ec,stroke:#E91E63
    style GAP4 fill:#e0f2f1,stroke:#009688
```

Only two boxes are genuinely new agent processes (pink). Everything blue and teal is a new tool/function bolted onto an agent that already exists.

---

## 8. Conversational Shopping

### 8a. Pre-search intelligence — guided narrowing, bundle search, reference resolution

```mermaid
flowchart LR
    A1(["Shopper types or speaks a query"]) --> B1["extract_structured_intent\nGemini Flash"]
    B1 --> C1{"Reference to prior turn?\ne.g. it / that one"}
    C1 -->|"Yes"| D1["resolve_reference\nagainst session.intent_history"]
    C1 -->|"No"| E1{"2+ intent fields null\nAND query under 6 words?"}
    D1 --> E1
    E1 -->|"Yes"| F1["Ask ONE clarifying question\nGemini Flash"]
    F1 -->|"Shopper answers"| G1["Merge answer into\nStructuredIntent"]
    E1 -->|"No"| H1{"is_multi_item\nflag set?"}
    G1 --> H1
    H1 -->|"Yes"| I1["decompose_use_case\nGemini Flash to sub-needs array"]
    I1 --> J1["Python: budget_share x total\nto hard max_price per sub-need"]
    J1 --> K1["Run vector_search_catalog\nonce PER sub-need"]
    H1 -->|"No"| L1["Run vector_search_catalog\nonce, existing path"]
    K1 --> M1["Python: sum bundle total\nnever LLM-stated"]
    L1 --> N1["Grounded explanation\nGemini Flash"]
    M1 --> N1
    N1 --> O1(["Result cards or bundle shown"])

    style A1 fill:#2196F3,color:#fff
    style O1 fill:#4CAF50,color:#fff
    style F1 fill:#9C27B0,color:#fff
    style I1 fill:#9C27B0,color:#fff
```

**Key conditions:** clarifying question only fires on short + ambiguous queries (never adds a turn to an already-specific query) · bundle total is always the Python sum, never a number Gemini states · a sub-need with no match is shown as a gap, never silently dropped.

### 8b. Cart concierge — checkout-time policy Q&A

```mermaid
flowchart TD
    A2(["Shopper asks a question from cart or checkout UI"]) --> B2["POST /cart/ask\nmessage + cart + store_id"]
    B2 --> C2["Gemini Flash decides\nwhich tool to call"]
    C2 --> D2{"Question type?"}
    D2 -->|"Product attribute"| E2["get_sku_details\nexisting tool"]
    D2 -->|"Policy, shipping, returns"| F2["get_store_policy\nNEW - reads static\nstore_policies/{store_id} doc"]
    D2 -->|"Both"| G2["Call both tools\nin same turn"]
    E2 --> H2
    F2 --> H2
    G2 --> H2
    H2{"Answer grounded\nin tool results?"}
    H2 -->|"Yes"| I2["Return grounded answer"]
    H2 -->|"No data returned"| J2["Honest, I do not know\nnever guesses"]
    I2 --> K2(["Shown inline in cart"])
    J2 --> K2

    style A2 fill:#2196F3,color:#fff
    style K2 fill:#4CAF50,color:#fff
    style J2 fill:#FF9800,color:#fff
```

**Key conditions:** never answers from general knowledge — only from what a tool call returned · a question needing both tools must call both in the same turn, not pick one.

---

## 9. Demand Planning

### 9a. Search-signal-to-forecast bridge

```mermaid
flowchart LR
    A3["Cloud Scheduler\nnightly trigger"] --> B3["Read insights collection\nstock_gap / discoverability_gap\nclusters, last N days"]
    B3 --> C3["Extract sku_id, occurrences,\ntrend_pct per cluster"]
    C3 --> D3["Write/update BigQuery table\ndaily_demand_signal:\nsales units + weighted\nunmet-demand term"]
    D3 --> E3[("BigQuery ML\nCREATE MODEL\nARIMA_PLUS")]
    E3 --> F3["ML.FORECAST\npredicted units + confidence\ninterval, per SKU per day"]
    F3 --> G3["Python parses rows into\nDemandForecast docs\none per SKU"]
    G3 --> H3[("Firestore\ndemand_forecasts")]
    H3 --> I3["Gemini Pro: ONE narrative\nsentence per SKU forecast\ngrounded on forecast_points only"]
    I3 --> J3["Merchant Dashboard\nonSnapshot listener"]
    D3 --> K3{"Fewer than MIN_DAYS\nof history for this SKU?"}
    K3 -->|"Yes"| L3["Omit forecast entirely\nnever guess"]

    style A3 fill:#E91E63,color:#fff
    style E3 fill:#FF9800,color:#fff
    style J3 fill:#009688,color:#fff
    style L3 fill:#f44336,color:#fff
```

**Why `ARIMA_PLUS` and not Vertex AI Forecast:** single `CREATE MODEL` statement against data already sitting in BigQuery event mirror — right-sized for the catalog.
**Key conditions:** LLM narrative never states a number absent from `forecast_points` · demand signal boost is always traceable to specific `insights` documents.

### 9b. Forecast-driven actions

```mermaid
flowchart TD
    A4[("Firestore\ndemand_forecasts")] --> B4{"Which trigger?"}

    B4 -->|"urgency_days crosses threshold\nAND forecast confirms\nrising demand"| C4["Auto-Reorder Draft"]
    C4 --> D4["Python: suggested_quantity =\ndaily_rate x lead_time x safety_factor"]
    D4 --> E4["Gemini: 1-sentence summary"]
    E4 --> F4["Write reorder_drafts doc\nconfirmed: false"]
    F4 --> G4{"Merchant taps Confirm?"}
    G4 -->|"Yes"| H4(["PO issued"])
    G4 -->|"No or ignored"| I4(["No inventory change"])

    B4 -->|"Merchant asks a what-if\ndiscount question in chat"| J4["simulate_price_change\nfunction call"]
    J4 --> K4["Python: new_price,\nelasticity constant\nper category, documented"]
    K4 --> L4{"Forecast exists\nfor this SKU?"}
    L4 -->|"No"| M4["insufficient_data\nGemini declines"]
    L4 -->|"Yes"| N4["Gemini narrates\nprojected revenue delta"]

    B4 -->|"Nightly, same job\nas forecast bridge"| O4["Cluster SKUs\nby category"]
    O4 --> P4["trend_pct at category level\nreuses existing formula"]
    P4 --> Q4["Fed into generate_brief\nas extra grounded field"]

    style A4 fill:#fce4ec,stroke:#E91E63
    style H4 fill:#4CAF50,color:#fff
    style M4 fill:#FF9800,color:#fff
```

**Key conditions:** auto-reorder needs *both* urgency AND forecast agreement before drafting · nothing touches inventory before human taps Confirm.

---

## 10. Fraud Detection & Risk Scoring

### 10a. Checkout risk scoring (synchronous)

```mermaid
flowchart TD
    A5(["Shopper starts checkout"]) --> B5["POST /checkout/start\nsession_id, device_id, cart"]
    B5 --> C5["Python queries Firestore directly\nNOT the BigQuery mirror -\ncheckout needs the freshest data"]
    C5 --> D5["Distinct shipping addresses\nfor device_id, last 24h"]
    C5 --> E5["Distinct sessions\nfor device_id, last 1h"]
    C5 --> F5["Cart total vs this device\nhistorical average order value"]
    D5 --> G5
    E5 --> G5
    F5 --> G5
    G5["Weighted rule sum\nnamed, documented weights -\nsame shape as return-risk scoring"]
    G5 --> H5{"Score"}
    H5 -->|"Under 25"| I5["Tier: LOW"]
    H5 -->|"25 to 49"| J5["Tier: MEDIUM"]
    H5 -->|"50 or more"| K5["Tier: HIGH"]
    I5 --> L5
    J5 --> L5
    K5 --> L5
    L5["Gemini Flash: 1 sentence\nnarrating factors ONLY -\nnever sees raw events,\nnever computes the score"]
    L5 --> M5["Write CheckoutRiskAssessment"]
    M5 --> N5{"Python decides the action"}
    N5 -->|"LOW or MEDIUM"| O5(["Checkout proceeds unaffected"])
    N5 -->|"HIGH"| P5(["Step-up verification prompt -\nnever a silent block"])
    C5 --> Q5{"First-time device,\nno history?"}
    Q5 -->|"Yes"| R5["Neutral score default -\nnot an extreme"]

    style A5 fill:#2196F3,color:#fff
    style O5 fill:#4CAF50,color:#fff
    style P5 fill:#FF9800,color:#fff
    style K5 fill:#f44336,color:#fff
```

**Key conditions:** score must be 100% reproducible from the same input (unit-testable) · high tier never silently blocks, only steps up verification.

### 10b. Pattern-level fraud signals

```mermaid
flowchart TD
    subgraph RAM["Return-Abuse Pattern Mining - nightly, reuses Insight pipeline"]
        A6[("return_assessments\ncollection")] --> B6["Python: GROUP BY shopper identity -\nnot semantic clustering"]
        B6 --> C6{"3+ high-risk-tier returns\nfor same shopper?"}
        C6 -->|"Yes"| D6["New signal_type:\nreturn_abuse_pattern"]
        C6 -->|"No"| E6["No signal"]
    end

    subgraph PROMO["Promo / Coupon Stacking - at promo-apply time"]
        F6["POST /cart/apply-promo"] --> G6["Python: other sessions sharing\ndevice_id or an email-alias pattern,\nalready used this code?"]
        G6 -->|"Match"| H6["Write PromoAbuseFlag\nlinking session IDs"]
        G6 -->|"No match"| I6["Discount applied normally"]
        H6 --> J6["Gemini narrates in merchant chat -\nNOT a real-time checkout block"]
    end

    subgraph CTR["Counterfeit Listing Screen - during Catalog Import Stage 2"]
        K6["Product image\nin import batch"] --> L6["Gemini Vision - narrow prompt:\nwatermarks, mismatched branding,\nduplicate reuse ONLY"]
        L6 --> M6{"needs_review flagged?"}
        M6 -->|"Yes"| N6["Confidence score capped -\nforced into admin preview step"]
        M6 -->|"No"| O6["Normal Stage 3 normalization"]
    end

    style D6 fill:#f44336,color:#fff
    style H6 fill:#FF9800,color:#fff
    style N6 fill:#FF9800,color:#fff
```

**Key conditions:** Vision pass in CTR only outputs plain visual reasoning — never a "counterfeit" label directly (human makes call in preview step) · promo stacking flags for review rather than blocking.

---

## 11. Deepened Insights Pipeline

```mermaid
flowchart LR
    A7["Trigger: on-demand / nightly\n/ weekly for digest"] --> B7["aggregate_events"]
    B7 --> C7[("Firestore Events")]
    C7 --> B7
    B7 --> D7["New grouping dimensions:\nplatform + returning-shopper flag"]
    D7 --> H7
    B7 --> F7["Gemini Pro: cluster by meaning"]
    F7 --> G7["Score in CODE"]
    G7 --> H7["Classify signal type"]
    I7["Crawler, reused from\nCatalog Import"] -.->|"competitor prices, nightly"| H7
    H7 --> J7["generate_brief\nGemini Pro, grounded"]
    J7 --> K7[("Firestore Insights")]
    L7["Event log,\npure Python counting"] --> M7["SKU co-occurrence\nCross-Sell Signal"]
    M7 --> J7
    K7 --> N7["Merchant Dashboard"]
    O7["Merchant chat\nfree-text question"] --> P7{"Why is X trending?"}
    P7 --> Q7["get_event_trend\nPython GROUP BY date"]
    Q7 --> R7["Gemini narrates\nday-by-day shape"]
    K7 --> S7{"Weekly scheduler"}
    S7 --> T7["Batch this run's briefs\ninto one digest"]
    T7 --> U7["Delivered via same stub\nas post-purchase follow-up"]

    style A7 fill:#E91E63,color:#fff
    style N7 fill:#009688,color:#fff
    style G7 fill:#FF9800,color:#fff
```

**Key conditions:** competitor price crawl is additive — falls back to budget-only comparison if no SKU match found · trend numbers strictly from Python `GROUP BY`.

---

## 12. Event Schema (Shared Across All Flows)

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

---

## 13. Diagram Color Key

| Color | Meaning |
|---|---|
| Blue | Entry point / trigger |
| Green | Successful, unblocked outcome |
| Orange | Guardrail branch — honest decline, review-required, or step-up flow |
| Red | Held-for-review / high-risk outcome |
| Purple | A point where Gemini generates something new (question, decomposition) rather than just retrieving or narrating |
