<div align="center">

# OffgridAI

### Turn every failed shopping journey into revenue.

**The closed-loop AI intelligence layer for modern commerce.**

[![Built with Gemini](https://img.shields.io/badge/Built%20with-Gemini-4285F4?logo=google)](https://ai.google.dev/)
[![Powered by Google Cloud](https://img.shields.io/badge/Powered%20by-Google%20Cloud-4285F4?logo=googlecloud)](https://cloud.google.com/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

[Explore the solution](docs/solution.md) · [View the architecture](docs/architecture.md) · [Review the roadmap](docs/implementation_plan.md)

</div>

---

## The commerce problem

Every day, shoppers leave because they cannot find what they want, discover their preferred product is unavailable, or purchase the wrong fit. Most commerce systems record these moments as disconnected events—and then forget them.

The result is a costly cycle of:

- **Failed discovery:** shoppers cannot translate intent into the right product.
- **Lost sales:** stockouts become dead ends instead of substitution opportunities.
- **Avoidable returns:** customers lack the guidance needed to buy confidently.
- **Invisible demand:** unmet customer intent never reaches the merchant.

> **The insight is already there. It is trapped inside the failure.**

## Our solution

OffgridAI detects when a shopping journey is about to fail, rescues it in real time, and converts the outcome into an actionable business signal.

It is a **platform-agnostic AI intelligence layer** that can sit between any customer experience and commerce backend—without requiring a retailer to replace its existing storefront, catalog, or operations stack.

```text
Customer intent
      ↓
Semantic discovery
      ↓
Failure detected? ── Yes ──► AI rescue
      │                              ↓
      No                       Outcome logged
      ↓                              ↓
Purchase                 Merchant insight generated
                                      ↓
                              Business action taken
```

This is the **Rescue Loop**: intent becomes action, failure becomes intelligence, and every interaction makes the next customer journey better.

## What OffgridAI does

### 1. Understand intent

Interpret text, images, voice, slang, synonyms, budget, attributes, use case, and urgency to create a structured shopper profile.

### 2. Discover without dead ends

Use semantic search to find relevant products—even when the exact query does not match the catalog. When the preferred item is unavailable, surface grounded alternatives with clear trade-offs.

### 3. Improve purchase confidence

For return-prone products, ask one targeted, SKU-specific fit question at the moment it matters.

### 4. Rescue stockouts

Combine substitutes, nearby inventory, and fulfillment timing to save revenue that would otherwise be lost.

### 5. Turn returns into value

Analyze a returned-item photo and order context to recommend whether the item should be restocked, refurbished, relisted, or liquidated.

### 6. Give merchants the signal

Cluster customer events, quantify revenue at risk, and produce plain-language briefs that merchants can act on.

## Three experiences, one intelligence layer

| Experience | What happens | Business outcome |
| --- | --- | --- |
| **Smart Discovery** | A vague query or product image becomes grounded, relevant recommendations. | More confident discovery and fewer zero-result journeys. |
| **Stockout Rescue** | An unavailable SKU becomes a transparent substitute, nearby-store option, or fulfillment alternative. | Revenue recovered instead of abandoned. |
| **Return-to-Value** | A return photo and order history become a disposition recommendation. | More recovered inventory value and better operations. |

## Built for the entire commerce team

- **Shoppers** get helpful answers instead of dead ends.
- **Store associates** get fast, practical return and inventory guidance.
- **Merchants** get demand intelligence from real customer behavior.
- **Commerce platforms** get an embeddable intelligence layer instead of another isolated application.

## Why OffgridAI is different

| Traditional commerce AI | OffgridAI |
| --- | --- |
| Search → recommend → buy | Intent → discover → rescue → fulfill → learn |
| Focuses on one customer interaction | Connects shopper, associate, and merchant workflows |
| Failed sessions disappear into logs | Failed intent becomes structured demand intelligence |
| Requires a single commerce platform | Integrates with any storefront, backend, or mobile experience |
| Gives generic recommendations | Gives catalog-grounded, explainable recommendations |

## Designed for trustworthy AI

OffgridAI is designed with grounding and measurable outputs at its core:

- Discovery and Fit-Check agents may describe only products retrieved from the catalog and identified by SKU.
- Insight agents may report only metrics computed from application data.
- Specialized agents are routed through an orchestrator rather than calling one another directly.
- Every rescue, fit-check, purchase, and return outcome is logged using a shared event schema.

## Platform-agnostic by design

Integrate OffgridAI wherever customers and commerce teams already work:

| Surface | Integration |
| --- | --- |
| Web storefront | Lightweight JavaScript embed |
| Backend | Language-agnostic REST API |
| Mobile app | Firebase SDK and real-time session sync |
| Store associate | Browser-based progressive web app |
| Messaging | Webhooks to the same REST API |

**One API. One event schema. Any commerce platform.**

## Technology

OffgridAI is designed on Google AI and Google Cloud:

- **Gemini via Vertex AI** — multimodal intent, fit-check, return analysis, and insight synthesis
- **Google Agent Development Kit** — orchestration and specialist agent routing
- **FastAPI on Cloud Run** — stateless, horizontally scalable API layer
- **Firestore** — sessions, catalog, events, and insights
- **Gemini Embeddings** — semantic catalog and query retrieval
- **BigQuery** — append-only event analytics and BI integration
- **Cloud Storage** — product, shelf, and return images
- **Firebase Hosting and Auth** — business surfaces and role-based access

See the complete [architecture diagram](docs/architecture.md) for system components and data flows.

## Repository

```text
OffgridAI/
├── backend/                 # Backend application scaffold
├── frontend/                # Frontend application scaffold
├── docs/
│   ├── solution.md          # Product vision and solution plan
│   ├── architecture.md     # System architecture and data flows
│   ├── implementation_plan.md
│   ├── backend_implementation_plan.md
│   ├── feasible_plan_v2.md
│   ├── flow_diagram.md
│   └── ticket_specs.md
├── LICENSE
└── README.md
```

## Get involved

The project is currently in the early implementation stage, with the product concept, architecture, implementation roadmap, and feature specifications documented in this repository.

```bash
git clone https://github.com/sanketp27/OffgridAI.git
cd OffgridAI
```

Start here:

1. Read the [solution plan](docs/solution.md) to understand the product and demo flows.
2. Review the [architecture](docs/architecture.md) to understand the system design.
3. Follow the [implementation plan](docs/implementation_plan.md) for the build roadmap.

## The vision

Commerce should not treat a failed search, a stockout, or a return as the end of the story.

**OffgridAI turns those moments into the beginning of a better one.**

---

<div align="center">

**Intent in. Intelligence out.**

Built for the next generation of commerce experiences.

</div>

## License

OffgridAI is licensed under the [Apache License 2.0](LICENSE).

---

## Run the frontend locally

The shopper / merchant / associate UI lives in [`frontend/`](frontend/) (Next.js 16 + React 19 + TypeScript).

### Prerequisites

1. **Git** installed and this repo cloned.
2. **Node.js 20.9 or newer** (Node 22 LTS recommended). Check with:
   ```bash
   node -v
   npm -v
   ```
3. If you use **nvm** on Windows and still see an old Node (for example v14):
   ```bash
   nvm install 22
   nvm use 22
   node -v
   ```

### Steps

1. **Clone the repository** (skip if you already have it):
   ```bash
   git clone https://github.com/sanketp27/OffgridAI.git
   cd OffgridAI
   ```

2. **Enter the frontend app**:
   ```bash
   cd frontend
   ```

3. **Install dependencies**:
   ```bash
   npm install
   ```

4. **Configure environment** (optional for local demo — mocks are on by default):
   ```bash
   # Windows (PowerShell)
   Copy-Item .env.example .env.local

   # macOS / Linux
   cp .env.example .env.local
   ```
   Default `.env.local` values:
   ```bash
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
   NEXT_PUBLIC_USE_MOCK_API=true
   ```
   Keep `NEXT_PUBLIC_USE_MOCK_API=true` until the backend Cloud Run API is ready. To call a live API later, set it to `false` and point `NEXT_PUBLIC_API_BASE_URL` at your service URL.

5. **Start the development server**:
   ```bash
   npm run dev
   ```

6. **Open the app in your browser**:
   - Storefront (shopper): [http://localhost:3000](http://localhost:3000)
   - Merchant insights: [http://localhost:3000/merchant](http://localhost:3000/merchant)
   - Associate returns: [http://localhost:3000/associate](http://localhost:3000/associate)

7. **Stop the server** when finished: press `Ctrl+C` in the terminal.

### Useful commands

| Command | What it does |
| --- | --- |
| `npm run dev` | Start local Next.js (Turbopack) on port 3000 |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | Run ESLint |

### Quick demo path

1. On `/`, use suggestion **Vague hiking intent** (or search `waterproof hiking boots under 4000`).
2. Choose TrailGrip → answer the fit-check (for example **Size up to 9.5**).
3. Open `/merchant` → **Generate Insights**.
4. Optional: `/associate` → upload a photo + order ID → confirm disposition.

More detail: [`frontend/README.md`](frontend/README.md).
