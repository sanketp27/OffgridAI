# OffgridAI / OmniCommerce AI: System Architecture & Deep Module Design

## 1. System Vision & Alignment
OffgridAI transforms unstructured merchant assets (PDF spec sheets, supplier portals, DOCX, XLSX, raw images) into an **Autonomous, Agentic-Ready Commerce Core** within 60 seconds.

Beyond legacy PIM parsers, the system executes an end-to-end activation loop:
`Unstructured Raw Sources` → `Multimodal Extraction` → `Omnichannel Asset Synthesis` → `Semantic Agentic Graph` → `Instant Conversational Storefront`.

---

## 2. Core Design Principles (Deep Modules)
Adhering to strict `codebase-design` tenets:
* **Deep Modules over Shallow Wrappers**: Complex multimodal pipelines, LLM retries, taxonomy matching, and embeddings hidden behind compact, unambiguous interfaces.
* **The Seam Discipline**: External dependencies (Gemini API, Document Extractors, Cloud Storage, Database) are accessed through swappable adapters across explicit seams.
* **The Deletion Test**: Deleting an adapter isolates 3rd-party volatility; deleting an engine module forces massive behavioral complexity to resurface at callers.
* **Accept Dependencies, Return Results**: Pure data-in, data-out contracts without hidden global state or side effects, guaranteeing zero-friction testability.

---

## 3. High-Level Architecture & Seam Map

```
  ┌────────────────────────────────────────────────────────┐
  │                    HTTP / CLI Caller                   │
  └───────────────────────────┬────────────────────────────┘
                              │
                      [Public API Seam]
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │ 1. IngestionModule                                     │
  │    (Interface: ingest_catalog_source)                  │
  │    - Sniffs content bytes                              │
  │    - Dispatches to format-specific extractors          │
  │    - Emits unified RawExtraction payload               │
  └───────────────────────────┬────────────────────────────┘
                              │
                     [Raw Extraction Seam]
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │ 2. StructuringAndEnrichmentModule                      │
  │    (Interface: structure_and_enrich)                   │
  │    - Gemini Flash Multimodal structuring               │
  │    - Business validation & content hashing             │
  │    - Omnichannel Asset Generation (Amazon, SEO, TikTok)│
  └─────────────┬────────────────────────────┬─────────────┘
                │                            │
      [Catalog Storage Seam]       [Graph Synthesis Seam]
                ▼                            ▼
  ┌───────────────────────────┐┌───────────────────────────┐
  │ StoreAdapter              ││ 3. AgenticGraphModule     │
  │ (Firestore / InMemory)    ││    (build_commerce_graph) │
  └───────────────────────────┘│    - Vector embeddings    │
                               │    - Bundle & compatibility│
                               │    - Semantic graph index │
                               └─────────────┬─────────────┘
                                             │
                                    [Storefront Agent Seam]
                                             ▼
                               ┌───────────────────────────┐
                               │ 4. ActivationStorefront   │
                               │    (query_commerce_agent) │
                               │    - Conversational Search│
                               │    - Autonomous Cart Tool │
                               └───────────────────────────┘
```

---

## 4. Deep Module Specifications

### Module 1: IngestionModule
* **Purpose**: Ingest any supported source format (PDF, DOCX, XLSX, Image, or Scraped URL) and produce normalized, structured text and image candidates.
* **Interface**:
  ```python
  class IngestionModule(Protocol):
      def ingest_source(self, source: IngestionSource) -> RawExtraction:
          """
          Takes raw binary bytes or URL source.
          Returns unified raw text blocks, extracted candidate image binaries,
          and metadata coordinates without leaking extraction internals.
          """
          ...
  ```
* **Depth & Hiding**:
  * Hides: PyMuPDF bounding-box xref parsing, openpyxl cell-anchored image geometry, docx media order resolution, web scraping DOM cleanup.
  * Invariants: Always returns normalized UTF-8 text and deduplicated binary image candidates with source provenance.
* **Seams & Adapters**:
  * `ExtractorAdapter`: Concrete extractors for PDF, DOCX, XLSX, Image, URL.
  * Test Adapter: `InMemoryExtractor` returning deterministic dummy text/images.

### Module 2: StructuringAndEnrichmentModule
* **Purpose**: Convert raw unstructured extraction into platform-standard SKUs and generate omnichannel syndication assets (Gap B).
* **Interface**:
  ```python
  class StructuringAndEnrichmentModule(Protocol):
      def structure_and_enrich(
          self,
          raw: RawExtraction,
          channels: list[OmnichannelTarget]
      ) -> EnrichmentResult:
          """
          Parses SKUs via Gemini Multimodal, validates business constraints,
          hashes content for idempotency, and synthesizes channel-tailored copy.
          """
          ...
  ```
* **Depth & Hiding**:
  * Hides: Gemini prompt choreography, JSON Schema enforcement, retry with exponential backoff, GS1 taxonomy mapping, Amazon A+ bullet formatting, TikTok marketing hook generation.
  * Invariants: Every product has a valid title, normalized price, category, content hash, and high-confidence image binding. Products failing hard schema validation are flagged with precise diagnostic codes.
* **Seams & Adapters**:
  * `GeminiModelAdapter`: Live Google GenAI API client vs `MockGeminiAdapter` returning golden fixtures.
  * `StorageAdapter`: GCS bucket for candidate images vs local file storage.

### Module 3: AgenticGraphModule
* **Purpose**: Transform flat product catalogs into an interconnected Semantic Knowledge Graph for agentic reasoning (Gap A).
* **Interface**:
  ```python
  class AgenticGraphModule(Protocol):
      def index_catalog(self, catalog: EnrichedCatalog) -> GraphIndexSummary:
          """
          Generates dense vector embeddings and infers cross-product
          relationships (compatibility, bundles, substitutes, target personas).
          """
          ...

      def find_semantic_solutions(
          self,
          intent: CustomerIntent,
          constraints: SearchConstraints
      ) -> list[SolutionBundle]:
          """
          Resolves multi-criteria queries with reasoning over graph edges.
          """
          ...
  ```
* **Depth & Hiding**:
  * Hides: `text-embedding-004` batch calls, vector distance search, graph relationship reasoning, bundle pricing calculation.
  * Invariants: All graph edges maintain strict directional semantic types (`COMPATIBLE_WITH`, `UPGRADE_OF`, `BUNDLE_ACCESSORY`).

### Module 4: ActivationStorefrontModule
* **Purpose**: Zero-Day customer-facing conversational shopping interface driven by the onboarded catalog and graph.
* **Interface**:
  ```python
  class ActivationStorefrontModule(Protocol):
      def chat(self, session: StorefrontSession, input_message: str) -> AgentTurnResponse:
          """
          Autonomous shopping conversational loop with tool-calling
          for catalog search, product inspection, and cart updates.
          """
          ...
  ```
* **Depth & Hiding**:
  * Hides: Conversation memory management, tool execution (cart manipulation, spec comparison), multimodal audio/voice parsing.

---

## 5. Persistence & Cloud Seams
* **Store Seam**:
  * `CatalogRepository`: Protocol with `upsert_products(list[Product]) -> UpsertReport` and `get_product(sku: str) -> Product`.
  * Production Adapter: Firestore / Cloud SQL.
  * Test Adapter: `InMemoryCatalogRepository`.
* **Deployment Topology (GCP)**:
  * Application runs on **Google Cloud Run** (stateless container).
  * Storage: **Google Cloud Storage** for source assets/images.
  * Database: **Cloud Firestore** for catalog state & graph relations.
  * AI Layer: **Gemini 2.0 / 1.5 Flash + text-embedding-004** via `google-genai` SDK.
