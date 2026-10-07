# OffGrid AI: Hackathon Implementation & Execution Plan

## 1. Project Overview & Deadlines
* **Target Event**: AI Builder Cup 2026 (Theme: Retail & Commerce)
* **Submission Deadline**: October 18, 2026
* **Required Deliverables**:
  1. Live Working Prototype deployed on GCP (Cloud Run / Firebase)
  2. Public GitHub Repository with clean architecture, tests, and documentation
  3. Video Demo under 3 minutes demonstrating the closed-loop rescue flows
  4. Pitch Deck detailing problem alignment, architecture, and retail impact

---

## 2. Sprint Timeline & Work Packages

```
   Days 1-3          Days 4-5          Days 6-7          Days 8-9          Days 10-11
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Phase 1:    │──▶│ Phase 2:    │──▶│ Phase 3:    │──▶│ Phase 4:    │──▶│ Phase 5:    │
│ Seams &     │   │ Stockout    │   │ Return      │   │ Demand      │   │ Deploy, Demo│
│ Discovery   │   │ Rescue      │   │ Intelligence│   │ Insights    │   │ & Deck      │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

### Phase 1: Core Seams & Conversational Discovery (Days 1–3) [Priority 1]
* **Goal**: Establish core deep module interfaces, seed standard product catalog data, and build conversational discovery with proactive fit checks.
* **Tasks**:
  * Set up `src/offgrid/` modular package layout with strict typing and Pydantic models.
  * Seed product catalog fixtures with standard attributes (clothing, footwear, electronics).
  * Implement `IntentAndDiscoveryModule`:
    * Multimodal query parsing with Gemini Flash.
    * Vector similarity retrieval using `text-embedding-004`.
    * Grounded response generation citing exact SKU IDs.
  * Implement `evaluate_fit()`: Sizing clarification question for high-return categories.
* **Testing**:
  * Unit tests against `InMemoryCatalogRepository` and `MockGeminiModelAdapter`.
  * Validate anti-hallucination guarantee: Zero responses containing hallucinated SKUs.

### Phase 2: Real-Time Stockout Rescue Engine (Days 4–5) [Priority 1]
* **Goal**: Enable automated detection of out-of-stock items, regional store inventory lookup, and trade-off substitution.
* **Tasks**:
  * Implement `StockoutRescueModule`:
    * Multi-store inventory availability queries.
    * Substitute ranking algorithm based on category attributes and price proximity.
    * Gemini Flash trade-off synthesis (price, shipping timing, color/size variance).
  * Build telemetry event emitter for session outcomes (`substitute_accepted`, `rescue_declined`, `stockout_lost`).
* **Testing**:
  * Test stockout rescue scenarios with mock multi-store inventory.
  * Validate trade-off prompt grounding with deterministic fixtures.

### Phase 3: Multimodal Return Intelligence (Days 6–7) [Priority 2]
* **Goal**: Deploy vision-based return inspection and deterministic disposition routing.
* **Tasks**:
  * Implement `ReturnIntelligenceModule`:
    * Gemini Flash Vision integration for condition grading (wear, damage, missing tags).
    * Heuristic fraud detection (wardrobing indicators, serial number mismatch).
    * Deterministic disposition engine (Restock, Refurbish at markdown, Liquidate, Hold).
  * Build lightweight Associate PWA (Firebase Hosting) for mobile photo capture and routing verdicts.
* **Testing**:
  * Unit tests with sample return photo fixtures across all 4 disposition states.
  * Verify disposition decisions are 100% code-driven without LLM business logic hallucination.

### Phase 4: Closed-Loop Demand Insights & Merchant Dashboard (Days 8–9) [Priority 2]
* **Goal**: Turn session logs and unmet demand telemetry into actionable merchant briefs.
* **Tasks**:
  * Implement `DemandInsightModule`:
    * Clustering algorithm for failed searches and unmet intent queries.
    * Deterministic revenue-at-risk formula calculations.
    * Gemini Pro grounded brief generation.
  * Build Merchant Dashboard view:
    * High-level metrics: revenue saved via rescue, returns mitigated, unmet demand lost.
    * "Generate Insights" trigger producing structured merchant briefs.
* **Testing**:
  * Test insight generation against simulated session logs.
  * Verify all revenue numbers in generated briefs strictly match code calculation outputs.

### Phase 5: Cloud Run Deployment, Video & Pitch (Days 10–11)
* **Goal**: Deploy working prototype on Google Cloud Run and finalize competition materials.
* **Tasks**:
  * Containerize application (`Dockerfile`) and deploy API to Google Cloud Run.
  * Host frontend demo surfaces on Firebase Hosting.
  * Run automated end-to-end integration tests across all three core scenarios.
  * Record <3-minute high-impact demo video:
    * 0:00–0:25 The problem: $300B discovery loss, $890B returns, stockout dead-ends.
    * 0:25–1:05 Live demo: Scenario 1 (Discovery & Fit-Check).
    * 1:05–1:40 Live demo: Scenario 2 (Stockout Rescue & Trade-Offs).
    * 1:40–2:15 Live demo: Scenario 3 (Associate Return Vision Inspection).
    * 2:15–2:45 Merchant Dashboard: Revenue-at-risk demand insights generated live.
    * 2:45–3:00 Architecture overview: Deep modules, Gemini Flash/Pro, Cloud Run.
  * Finalize slide deck and submit to the AI Builder Cup portal.

---

## 3. Risk Management & Mitigations
* **Risk: LLM Hallucinations in Catalog Recommendations**
  * *Mitigation*: Hard anti-hallucination constraint requiring citations of existing SKU IDs fetched from the repository.
* **Risk: Gemini API Latency on Interactive Turns**
  * *Mitigation*: Use Gemini 2.x/1.5 Flash with minimal system prompts for interactive shopper and associate turns; reserve Gemini Pro for asynchronous batch insight generation.
* **Risk: Cold Starts on Cloud Run**
  * *Mitigation*: Lightweight FastAPI runtime, minimal container image footprint, and min-instances set to 1 during judging.
