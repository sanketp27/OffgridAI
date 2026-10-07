# OffGrid AI: System Architecture & Deep Module Design

## 1. System Vision & Alignment
OffGrid AI is a platform-agnostic, embeddable intelligence layer for modern retail and commerce. It detects when a customer shopping journey or post-purchase experience is about to break down, executes real-time AI rescue, and feeds operational telemetry back into merchant inventory and demand planning.

The architecture connects five specialized agents across a closed-loop flywheel:
`Customer Intent / Session Telemetry` → `Conversational Discovery & Fit-Check` → `Stockout Rescue & Substitution` → `Multimodal Return Intelligence` → `Merchant Demand Insights`.

---

## 2. Core Design Principles (Deep Modules)
Adhering to strict `codebase-design` principles:
* **Deep Modules over Shallow Wrappers**: Complex multimodal processing, multi-criteria vector retrieval, substitute scoring, and telemetry clustering are hidden behind small, well-defined module contracts.
* **The Seam Discipline**: External systems (Google Gemini API, Firestore, Cloud Storage, BigQuery) connect via explicit seams and swappable adapters.
* **The Deletion Test**: Swapping or deleting an adapter changes an external dependency; deleting a core engine module would force massive business and agentic logic to resurface at callers.
* **Accept Dependencies, Return Results**: Pure data-in, data-out contracts with no hidden state or global side-effects, guaranteeing straightforward unit and regression testing.
* **Anti-Hallucination Invariants**: Product suggestions must cite concrete catalog SKU IDs; insight metrics must be computed deterministically in code before being phrased by LLMs.

---

## 3. High-Level Architecture & Seam Map

```
   ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
   │    Shopper Widget     │ │     Associate PWA     │ │   Merchant Dashboard  │
   │  (JS Embed / Mobile)  │ │   (Return Inspection) │ │   (Demand Telemetry)  │
   └───────────┬───────────┘ └───────────┬───────────┘ └───────────┬───────────┘
               │                         │                         │
               └─────────────────────────┼─────────────────────────┘
                                         ▼
                                 [Public REST API Seam]
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│ 1. Intent & Discovery   │  │ 2. Stockout Rescue      │  │ 3. Return Intelligence  │
│    Module               │  │    Module               │  │    Module               │
│ - Intent parsing        │  │ - Local inventory check │  │ - Gemini Vision audit   │
│ - Semantic search       │  │ - Trade-off explanation │  │ - Fraud detection       │
│ - Fit-check trigger     │  │ - Cart swap resolution  │  │ - Deterministic routing │
└───────────┬─────────────┘  └───────────┬─────────────┘  └───────────┬─────────────┘
            │                            │                            │
            └────────────────────────────┼────────────────────────────┘
                                         │
                                [Telemetry Event Seam]
                                         ▼
                             ┌─────────────────────────┐
                             │ 4. Demand Insight       │
                             │    Module               │
                             │ - Session clustering    │
                             │ - Revenue-at-risk math  │
                             │ - Grounded brief writer │
                             └───────────┬─────────────┘
                                         │
                                 [Storage & Model Seams]
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  Catalog / Inventory Seam      Telemetry Seam            AI Model Seam      │
  │  Firestore / InMemory          BigQuery / Firestore      Gemini Flash / Pro │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Deep Module Specifications

### Module 1: IntentAndDiscoveryModule
* **Purpose**: Parse raw customer queries (text, voice, photo) into structured intent, perform vector discovery over catalog SKUs, and execute proactive fit-checks on return-prone categories.
* **Interface**:
  ```python
  class IntentAndDiscoveryModule(Protocol):
      def search(self, session: SessionContext, query: CustomerQuery) -> DiscoveryResult:
          """
          Extracts structured attributes, searches catalog vectors, and returns
          ranked SKUs with grounded match reasons.
          """
          ...

      def evaluate_fit(self, sku_id: str, shopper_profile: ShopperProfile) -> FitCheckPrompt | None:
          """
          Evaluates if SKU is return-prone and returns a single targeted clarifying
          question if sizing or compatibility ambiguity exists.
          """
          ...
  ```
* **Depth & Hiding**: Hides embedding generation, vector distance metrics, category-specific fit risk rules, and Gemini Flash dialogue prompt orchestration.
* **Invariants**: Guarantees zero empty dead-ends; any low-confidence match falls back to near-match alternatives with plain-language explanations.

### Module 2: StockoutRescueModule
* **Purpose**: Intercept out-of-stock SKU requests, inspect regional store inventory, rank substitute items, and synthesize actionable trade-off explanations.
* **Interface**:
  ```python
  class StockoutRescueModule(Protocol):
      def rescue_stockout(
          self,
          out_of_stock_sku: str,
          location: CustomerLocation,
          constraints: SubstitutionConstraints
      ) -> RescueOffer:
          """
          Finds in-stock substitutes or nearby store inventory and generates
          clear trade-off comparisons (price delta, delivery timing, spec differences).
          """
          ...
  ```
* **Depth & Hiding**: Hides regional store radius queries, inventory reconciliation, substitute compatibility scoring, and customer-facing trade-off copy synthesis.
* **Invariants**: Never recommends out-of-stock substitutes; trade-offs are grounded in verified stock data.

### Module 3: ReturnIntelligenceModule
* **Purpose**: Inspect returned items using multimodal vision, evaluate condition and fraud indicators, and assign deterministic disposition routing.
* **Interface**:
  ```python
  class ReturnIntelligenceModule(Protocol):
      def inspect_return(
          self,
          item_image: ImagePayload,
          order_record: OrderRecord
      ) -> DispositionDecision:
          """
          Evaluates item condition, detects anomalies/fraud signals, and returns
          disposition recommendation (Restock, Refurbish, Liquidate, Hold).
          """
          ...
  ```
* **Depth & Hiding**: Hides Gemini Flash Vision prompt templates, damage classification heuristics, policy abuse risk scoring, and depreciation calculations.
* **Invariants**: Business routing (refund approval thresholds and markdown levels) is executed in deterministic code, never hallucinated by the LLM.

### Module 4: DemandInsightModule
* **Purpose**: Aggregate closed-loop session telemetry, identify unmet customer demand, compute revenue at risk, and generate actionable briefs for merchants.
* **Interface**:
  ```python
  class DemandInsightModule(Protocol):
      def generate_insights(
          self,
          time_window: TimeRange,
          filter_criteria: InsightFilter
      ) -> list[DemandInsightBrief]:
          """
          Clusters failed search sessions, calculates revenue-at-risk figures,
          and writes grounded merchant action recommendations.
          """
          ...
  ```
* **Depth & Hiding**: Hides semantic clustering of search queries, statistical revenue-at-risk aggregation, and Gemini Pro grounded brief generation.
* **Invariants**: All revenue figures and search counts are computed in Python code; the LLM is restricted to narrative explanation of pre-calculated metrics.

---

## 5. Persistence & External Seams

* **Catalog & Inventory Seam**:
  * `ProductCatalogRepository`: Fetch product metadata and vector embeddings.
  * `InventoryRepository`: Query store-level stock status and delivery timeframes.
  * Test Adapters: `InMemoryCatalogRepository`, `InMemoryInventoryRepository`.
* **Telemetry Seam**:
  * `TelemetryLogger`: Logs session outcomes (`search_completed`, `stockout_rescued`, `fit_adjusted`, `unmet_demand_lost`).
  * Adapters: Cloud Firestore (live sync), BigQuery (batch analytical queries), InMemory (testing).
* **AI Model Seam**:
  * `GeminiModelAdapter`: Live `google-genai` client for Gemini 2.x/1.5 Flash (real-time turns) and Gemini Pro (insight generation) with exponential backoff.
  * Test Adapter: `MockGeminiModelAdapter` returning deterministic test fixtures.

---

## 6. GCP Deployment Topology
* **Compute**: Google Cloud Run (stateless container running the FastAPI service).
* **Frontends**: Firebase Hosting (Shopper Embed demo, Store Associate PWA, Merchant Dashboard).
* **Data & Storage**:
  * Cloud Firestore: Real-time inventory status, active sessions, product catalog.
  * Cloud Storage: Return inspection photos and media assets.
  * BigQuery: Long-term intent logs and demand telemetry.
* **AI & Orchestration**: Google GenAI SDK / Vertex AI Gemini Flash and Gemini Pro.
