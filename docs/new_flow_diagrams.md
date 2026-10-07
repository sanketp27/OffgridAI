# OffGrid AI — New Flow Diagrams
### Conversational Shopping · Demand Planning · Fraud · Insights

**Companion to `flow_diagram.md`.** Render with any Mermaid-compatible viewer (GitHub, GitLab, Obsidian, mermaid.live). Node and edge labels carry the tech (Gemini model, GCP service) and trigger conditions directly, same convention as the existing scenario diagrams — the diagram *is* the spec, not just an illustration of one.

---

## 0. Where these plug into the existing mesh

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
        DP0["Demand Planning Agent
Gemini Pro + BigQuery ML"]
        DP1["Forecast Bridge"]
        DP2["Auto-Reorder Draft"]
        DP3["Price Simulator"]
        DP4["Seasonal Brief"]
    end

    subgraph GAP3["Fraud - NEW agent"]
        FR0["Fraud Scoring Agent
Gemini Flash + Python rules"]
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

## 1. Conversational Shopping

### 1a. Pre-search intelligence — guided narrowing, bundle search, reference resolution

All three live inside the same intent-extraction step, which is why they're one diagram, not three.

```mermaid
flowchart LR
    A1(["Shopper types or speaks a query"]) --> B1["extract_structured_intent
Gemini Flash"]
    B1 --> C1{"Reference to prior turn?
e.g. it / that one"}
    C1 -->|"Yes"| D1["resolve_reference
against session.intent_history"]
    C1 -->|"No"| E1{"2+ intent fields null
AND query under 6 words?"}
    D1 --> E1
    E1 -->|"Yes"| F1["Ask ONE clarifying question
Gemini Flash"]
    F1 -->|"Shopper answers"| G1["Merge answer into
StructuredIntent"]
    E1 -->|"No"| H1{"is_multi_item
flag set?"}
    G1 --> H1
    H1 -->|"Yes"| I1["decompose_use_case
Gemini Flash to sub-needs array"]
    I1 --> J1["Python: budget_share x total
to hard max_price per sub-need"]
    J1 --> K1["Run vector_search_catalog
once PER sub-need"]
    H1 -->|"No"| L1["Run vector_search_catalog
once, existing path"]
    K1 --> M1["Python: sum bundle total
never LLM-stated"]
    L1 --> N1["Grounded explanation
Gemini Flash"]
    M1 --> N1
    N1 --> O1(["Result cards or bundle shown"])

    style A1 fill:#2196F3,color:#fff
    style O1 fill:#4CAF50,color:#fff
    style F1 fill:#9C27B0,color:#fff
    style I1 fill:#9C27B0,color:#fff
```

**Key conditions:** clarifying question only fires on short + ambiguous queries (never adds a turn to an already-specific query) · bundle total is always the Python sum, never a number Gemini states · a sub-need with no match is shown as a gap, never silently dropped.

### 1b. Cart concierge — checkout-time policy Q&A

```mermaid
flowchart TD
    A2(["Shopper asks a question from cart or checkout UI"]) --> B2["POST /cart/ask
message + cart + store_id"]
    B2 --> C2["Gemini Flash decides
which tool to call"]
    C2 --> D2{"Question type?"}
    D2 -->|"Product attribute"| E2["get_sku_details
existing tool"]
    D2 -->|"Policy, shipping, returns"| F2["get_store_policy
NEW - reads static
store_policies/{store_id} doc"]
    D2 -->|"Both"| G2["Call both tools
in same turn"]
    E2 --> H2
    F2 --> H2
    G2 --> H2
    H2{"Answer grounded
in tool results?"}
    H2 -->|"Yes"| I2["Return grounded answer"]
    H2 -->|"No data returned"| J2["Honest, I do not know
never guesses"]
    I2 --> K2(["Shown inline in cart"])
    J2 --> K2

    style A2 fill:#2196F3,color:#fff
    style K2 fill:#4CAF50,color:#fff
    style J2 fill:#FF9800,color:#fff
```

**Key conditions:** never answers from general knowledge — only from what a tool call returned · a question needing both tools must call both in the same turn, not pick one.

---

## 2. Demand Planning — currently the weakest category

### 2a. Search-signal-to-forecast bridge (the core new capability)

```mermaid
flowchart LR
    A3["Cloud Scheduler
nightly trigger"] --> B3["Read insights collection
stock_gap / discoverability_gap
clusters, last N days"]
    B3 --> C3["Extract sku_id, occurrences,
trend_pct per cluster"]
    C3 --> D3["Write/update BigQuery table
daily_demand_signal:
sales units + weighted
unmet-demand term"]
    D3 --> E3[("BigQuery ML
CREATE MODEL
ARIMA_PLUS")]
    E3 --> F3["ML.FORECAST
predicted units + confidence
interval, per SKU per day"]
    F3 --> G3["Python parses rows into
DemandForecast docs
one per SKU"]
    G3 --> H3[("Firestore
demand_forecasts")]
    H3 --> I3["Gemini Pro: ONE narrative
sentence per SKU forecast
grounded on forecast_points only"]
    I3 --> J3["Merchant Dashboard
onSnapshot listener"]
    D3 --> K3{"Fewer than MIN_DAYS
of history for this SKU?"}
    K3 -->|"Yes"| L3["Omit forecast entirely
never guess"]

    style A3 fill:#E91E63,color:#fff
    style E3 fill:#FF9800,color:#fff
    style J3 fill:#009688,color:#fff
    style L3 fill:#f44336,color:#fff
```

**Why `ARIMA_PLUS` and not Vertex AI Forecast:** the latter is built for 100M-row catalogs with years of history; `ARIMA_PLUS` is a single `CREATE MODEL` statement against data already sitting in the BigQuery event mirror you've already built — right-sized for a new catalog, with the same table structure carrying forward if you outgrow it.

**Key conditions:** the LLM narrative never states a number absent from `forecast_points` · demand signal boost is always traceable to specific `insights` documents (audit trail).

### 2b. Forecast-driven actions

```mermaid
flowchart TD
    A4[("Firestore
demand_forecasts")] --> B4{"Which trigger?"}

    B4 -->|"urgency_days crosses threshold
AND forecast confirms
rising demand"| C4["Auto-Reorder Draft"]
    C4 --> D4["Python: suggested_quantity =
daily_rate x lead_time x safety_factor"]
    D4 --> E4["Gemini: 1-sentence summary"]
    E4 --> F4["Write reorder_drafts doc
confirmed: false"]
    F4 --> G4{"Merchant taps Confirm?"}
    G4 -->|"Yes"| H4(["PO issued"])
    G4 -->|"No or ignored"| I4(["No inventory change"])

    B4 -->|"Merchant asks a what-if
discount question in chat"| J4["simulate_price_change
function call"]
    J4 --> K4["Python: new_price,
elasticity constant
per category, documented"]
    K4 --> L4{"Forecast exists
for this SKU?"}
    L4 -->|"No"| M4["insufficient_data
Gemini declines"]
    L4 -->|"Yes"| N4["Gemini narrates
projected revenue delta"]

    B4 -->|"Nightly, same job
as forecast bridge"| O4["Cluster SKUs
by category"]
    O4 --> P4["trend_pct at category level
reuses existing formula"]
    P4 --> Q4["Fed into generate_brief
as extra grounded field"]

    style A4 fill:#fce4ec,stroke:#E91E63
    style H4 fill:#4CAF50,color:#fff
    style M4 fill:#FF9800,color:#fff
```

**Key conditions:** auto-reorder needs *both* urgency AND forecast agreement before drafting — one noisy signal alone never triggers a PO draft · nothing touches inventory before a human taps Confirm.

---

## 3. Fraud — also a real gap

### 3a. Checkout risk scoring (the core new capability, synchronous)

```mermaid
flowchart TD
    A5(["Shopper starts checkout"]) --> B5["POST /checkout/start
session_id, device_id, cart"]
    B5 --> C5["Python queries Firestore directly
NOT the BigQuery mirror -
checkout needs the freshest data"]
    C5 --> D5["Distinct shipping addresses
for device_id, last 24h"]
    C5 --> E5["Distinct sessions
for device_id, last 1h"]
    C5 --> F5["Cart total vs this device
historical average order value"]
    D5 --> G5
    E5 --> G5
    F5 --> G5
    G5["Weighted rule sum
named, documented weights -
same shape as return-risk scoring"]
    G5 --> H5{"Score"}
    H5 -->|"Under 25"| I5["Tier: LOW"]
    H5 -->|"25 to 49"| J5["Tier: MEDIUM"]
    H5 -->|"50 or more"| K5["Tier: HIGH"]
    I5 --> L5
    J5 --> L5
    K5 --> L5
    L5["Gemini Flash: 1 sentence
narrating factors ONLY -
never sees raw events,
never computes the score"]
    L5 --> M5["Write CheckoutRiskAssessment"]
    M5 --> N5{"Python decides the action"}
    N5 -->|"LOW or MEDIUM"| O5(["Checkout proceeds unaffected"])
    N5 -->|"HIGH"| P5(["Step-up verification prompt -
never a silent block"])
    C5 --> Q5{"First-time device,
no history?"}
    Q5 -->|"Yes"| R5["Neutral score default -
not an extreme"]

    style A5 fill:#2196F3,color:#fff
    style O5 fill:#4CAF50,color:#fff
    style P5 fill:#FF9800,color:#fff
    style K5 fill:#f44336,color:#fff
```

**Why Python rules and not BigQuery ML anomaly detection:** anomaly models need meaningful volume of *normal* checkout history to model against, which a new system doesn't have yet, and their scores are hard to explain to a store associate. Named, weighted rules are explainable from day one — the same reasoning this project already applied once to return-risk tiering.

**Key conditions:** score must be 100% reproducible from the same input (unit-testable) · high tier never silently blocks — it only steps up verification.

### 3b. Pattern-level fraud signals

```mermaid
flowchart TD
    subgraph RAM["Return-Abuse Pattern Mining - nightly, reuses Insight pipeline"]
        A6[("return_assessments
collection")] --> B6["Python: GROUP BY shopper identity -
not semantic clustering"]
        B6 --> C6{"3+ high-risk-tier returns
for same shopper?"}
        C6 -->|"Yes"| D6["New signal_type:
return_abuse_pattern"]
        C6 -->|"No"| E6["No signal"]
    end

    subgraph PROMO["Promo / Coupon Stacking - at promo-apply time"]
        F6["POST /cart/apply-promo"] --> G6["Python: other sessions sharing
device_id or an email-alias pattern,
already used this code?"]
        G6 -->|"Match"| H6["Write PromoAbuseFlag
linking session IDs"]
        G6 -->|"No match"| I6["Discount applied normally"]
        H6 --> J6["Gemini narrates in merchant chat -
NOT a real-time checkout block"]
    end

    subgraph CTR["Counterfeit Listing Screen - during Catalog Import Stage 2"]
        K6["Product image
in import batch"] --> L6["Gemini Vision - narrow prompt:
watermarks, mismatched branding,
duplicate reuse ONLY"]
        L6 --> M6{"needs_review flagged?"}
        M6 -->|"Yes"| N6["Confidence score capped -
forced into admin preview step"]
        M6 -->|"No"| O6["Normal Stage 3 normalization"]
    end

    style D6 fill:#f44336,color:#fff
    style H6 fill:#FF9800,color:#fff
    style N6 fill:#FF9800,color:#fff
```

**Key conditions:** the Vision pass in CTR may only output a plain visual reason — it never outputs a "counterfeit" or "fraud" label; the human always makes that call in the preview step · promo stacking flags for review rather than blocking, since a shared household device is a real false-positive case.

---

## 4. Insights — deepened pipeline

One diagram: every item here is a new branch feeding the same `generate_brief` step your Insight Agent already has, not a parallel pipeline.

```mermaid
flowchart LR
    A7["Trigger: on-demand / nightly
/ weekly for digest"] --> B7["aggregate_events"]
    B7 --> C7[("Firestore Events")]
    C7 --> B7
    B7 --> D7["New grouping dimensions:
platform + returning-shopper flag"]
    D7 --> H7
    B7 --> F7["Gemini Pro: cluster by meaning"]
    F7 --> G7["Score in CODE"]
    G7 --> H7["Classify signal type"]
    I7["Crawler, reused from
Catalog Import"] -.->|"competitor prices, nightly"| H7
    H7 --> J7["generate_brief
Gemini Pro, grounded"]
    J7 --> K7[("Firestore Insights")]
    L7["Event log,
pure Python counting"] --> M7["SKU co-occurrence
Cross-Sell Signal"]
    M7 --> J7
    K7 --> N7["Merchant Dashboard"]
    O7["Merchant chat
free-text question"] --> P7{"Why is X trending?"}
    P7 --> Q7["get_event_trend
Python GROUP BY date"]
    Q7 --> R7["Gemini narrates
day-by-day shape"]
    K7 --> S7{"Weekly scheduler"}
    S7 --> T7["Batch this run's briefs
into one digest"]
    T7 --> U7["Delivered via same stub
as post-purchase follow-up"]

    style A7 fill:#E91E63,color:#fff
    style N7 fill:#009688,color:#fff
    style G7 fill:#FF9800,color:#fff
```

**Key conditions:** competitor price crawl is additive — if no reliable SKU match is found, the classifier falls back to budget-only comparison exactly as it does today · trend drilldown numbers always come from the Python `GROUP BY`, Gemini only narrates the shape.

---

## Reading the color key (consistent across all diagrams above)

| Color | Meaning |
|---|---|
| Blue | Entry point / trigger |
| Green | Successful, unblocked outcome |
| Orange | Guardrail branch — honest decline, review-required, or step-up flow |
| Red | Held-for-review / high-risk outcome |
| Purple | A point where Gemini generates something new (question, decomposition) rather than just retrieving or narrating |

*Companion documents: `flow_designs.md` (prose spec — what/how/tech/conditions for each flow), `flow_diagram.md`, `architecture.md`, `backend_implementation_plan.md`.*
