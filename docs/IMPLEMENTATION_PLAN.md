# OffgridAI: Hackathon Implementation & Execution Plan

## 1. Project Overview & Deadlines
* **Target Event**: AI Builder Cup 2026 (Theme: Retail & Commerce)
* **Submission Deadline**: October 18, 2026 (11-day build window)
* **Required Deliverables**:
  1. Live Working Prototype deployed on GCP (Cloud Run / Firebase)
  2. Public GitHub Repository with clean documentation and tests
  3. Video Demo under 3 minutes
  4. Pitch Deck explaining problem alignment, architecture, and business impact

---

## 2. Sprint Timeline & Work Packages

```
   Days 1-3          Days 4-5          Days 6-8          Days 9-10          Day 11
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Phase 1A:   │──▶│ Phase 1B:   │──▶│ Phase 2:    │──▶│ Phase 3:    │──▶│ Phase 4:    │
│ Ingestion & │   │ Omnichannel │   │ Agentic     │   │ Storefront  │   │ Deploy, Demo│
│ Core Parser │   │ Enrichment  │   │ Graph Engine│   │ Demo UI     │   │ & Deck      │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

### Phase 1A: Core Ingestion & Normalization (Days 1–3) [Priority 1]
* **Goal**: Establish deep `IngestionModule` and wire existing `catalogue_parser` assets into the clean seam architecture.
* **Tasks**:
  * Unpack and reorganize `docs/catalogue_parser.zip` into `src/offgrid/`.
  * Establish `IngestionSource` abstraction (PDF, DOCX, XLSX, Images, URL scraper).
  * Formalize `RawExtraction` Pydantic models.
  * Integrate `google-genai` SDK for Gemini Flash structured SKU extraction.
  * Implement `validate_batch()` with content hashing for idempotent deduplication.
* **Testing**:
  * Unit tests against fixture files (`sample_catalogue.pdf`, `.xlsx`, `.docx`).
  * Verify 100% extraction accuracy on SKU titles, specs, prices, and image binds.

### Phase 1B: Omnichannel Enrichment Engine (Days 4–5) [Priority 1 + Gap B]
* **Goal**: Upgrade parser into an autonomous merchant enablement tool.
* **Tasks**:
  * Build `OmnichannelEnricher` module behind `StructuringAndEnrichmentModule`.
  * Implement channel prompt transforms:
    * **Amazon A+ Content**: Bullet points, technical specifications, compliance disclosures.
    * **Shopify / Web SEO**: Meta title, meta description, alt tags, schema.org JSON-LD.
    * **Social / TikTok Shop**: Engaging short hooks, target audience tags, key USPs.
  * Implement taxonomy classifier: Map raw categories to GS1 / Google Product Taxonomy standard.
* **Testing**:
  * Test omnichannel output generation with mock Gemini adapter and live Gemini 2.0 Flash.

### Phase 2: Semantic Agentic Graph (Days 6–8) [Priority 2 + Gap A]
* **Goal**: Transform flat catalog records into an interconnected knowledge graph for M2M agent reasoning.
* **Tasks**:
  * Integrate `text-embedding-004` to create vector embeddings for all enriched SKUs.
  * Build relationship inference pipeline:
    * Cross-product compatibility (e.g., lens fits camera body).
    * Bundle recommendations & accessories.
    * Customer persona & intent tags.
  * Implement `AgenticGraphModule` interface with `find_semantic_solutions()` query method.
* **Testing**:
  * Test semantic retrieval on multi-criteria prompts ("bundle for beginner vlogger under $500").

### Phase 3: Instant Storefront Demo Interface (Days 9–10) [Stretch / Priority 3]
* **Goal**: Interactive visual UI demonstrating the zero-to-live merchant activation journey.
* **Tasks**:
  * Build lightweight FastAPI / Streamlit / Next.js web application:
    * **Merchant View**: Drag-and-drop catalog upload (PDF/XLSX/URL) → live progress stream → inspected SKU table & omnichannel previews.
    * **Shopper View (Zero-Day Storefront)**: Real-time interactive search querying the newly onboarded graph, showcasing AI recommendations and cart assembly.
* **Testing**:
  * Full end-to-end loop: Upload PDF on Merchant side → instantly query on Shopper side.

### Phase 4: Cloud Run Deployment, Video & Pitch (Day 11)
* **Goal**: Finalize submission package and guarantee zero downtime during judging.
* **Tasks**:
  * Containerize application (`Dockerfile`) optimized for Google Cloud Run.
  * Deploy to Cloud Run with GCP secret manager for API keys.
  * Record <3-minute high-impact demo video:
    * 0:00–0:30 Problem statement: Merchant onboarding friction & static catalog limits.
    * 0:30–1:45 Live demo: Upload messy PDF → instant extraction & omnichannel assets → instant shopper query.
    * 1:45–2:30 Architecture overview: Deep modules, Gemini Flash + Embeddings, Cloud Run scalability.
    * 2:30–3:00 Business impact & metrics.
  * Finalize slide deck and submit on the AI Builder Cup portal.

---

## 3. Risk Management & Mitigations
* **Risk: Gemini API Rate Limits during bulk parsing**
  * *Mitigation*: Batch requests, local chunk caching, and exponential backoff.
* **Risk: Cloud Run cold starts / deployment errors**
  * *Mitigation*: Test container deployment on Day 5 and Day 8, well before final deadline.
* **Risk: Scope creep on conversational voice frontend**
  * *Mitigation*: Keep Storefront as a clean, responsive web chat/search interface consuming the deep graph module; voice can be progressive enhancement if time allows.
