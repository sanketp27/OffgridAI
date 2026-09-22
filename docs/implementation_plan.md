# OffGrid AI — Implementation Plan (Plan A: Full Build)

**Retail & Commerce: Intelligent Customer and Business Experiences**
Hackathon Submission | Google AI + Google Cloud

---

## 1. Purpose

This is the execution plan for the full OffGrid architecture described in `solution.md`, `flow_diagram.md`, and `architecture.md`, with the fixes from the architecture review baked in from the start rather than patched on later. It assumes a team that can realistically staff the full five-agent scope. If your team or timeline can't support that, use `feasible_plan_v2.md` instead — it's a strict subset of this same data model, not a different product.

**Assumptions** (adjust to your actual constraints):
- Team of 2–4 people
- ~6-day build window before submission
- One person can own infra/data while others build agents in parallel from Day 2 onward

**Total estimated effort:** ~89 hours for the P0 core + ~42.5 hours for full P1/P2 stretch scope (~131 hours total), split across two stretch tracks — feature extensions (Phase 5A, ~17.5 hrs) and new scenarios (Phase 5B, ~25 hrs). See `offgrid_tickets.xlsx` for the per-ticket breakdown and the Summary sheet for live totals.

---

## 2. Fixes from architecture review — baked into this plan, not bolted on

These were flagged in review and are addressed at the ticket level (see tickets OG-040 to OG-042), not left as follow-up cleanup:

| Issue | Resolution in this plan |
|---|---|
| Intent Agent + Discovery Agent as two serial LLM calls | Collapsed into one Gemini Flash function-calling turn (Ticket OG-012) |
| Scenario 3 claimed fraud signals come from a return photo | Split into two grounded signals: photo → condition only; order-history features in code → return-risk score (OG-038, OG-041) |
| Disposition agent implied automatic RESTOCK/REFURBISH/LIQUIDATE actions | Recommendations only — associate must confirm in the PWA (OG-039) |
| Duplicate Mermaid node ID `S3` in Scenario 3 flow | Renamed before any diagram is rendered for the deck (OG-040) |
| "Platform-agnostic" claims (Shopify, WooCommerce, POS, WhatsApp, mobile) all presented as equally real | Deck explicitly marks which are demoed vs. architected-for (OG-045, OG-046) |
| Leftover filename `omnirerescue.js` inconsistent with product name | Renamed for consistency (OG-042) |

---

## 3. Build phases

### Phase 0 — Environment setup (Day 1, morning)
**Goal:** a deployable skeleton exists before any agent logic is written.
- GCP project created, billing enabled, Vertex AI / Cloud Run / Firestore APIs enabled
- Firebase project initialized (Hosting, Firestore, Auth)
- A "hello world" FastAPI service deployed to Cloud Run — proves the deploy pipeline works before it's load-bearing
- One successful local call to Gemini Flash confirms auth is wired correctly
**Exit criteria:** you can deploy a change and see it live in under 5 minutes.

### Phase 1 — Data & content prep (Day 1)
**Goal:** every downstream agent has real data to work against; nothing is designed around data you don't have yet.
- Catalog seeded (300–500 SKUs) with `return_rate` populated by category
- Catalog embeddings generated
- ~50 synthetic shopper queries generated (deliberately including vague, misspelled, and zero-result cases)
- Multi-store stock matrix synthesized (only if you're building the Stockout Rescue stretch — Phase 5)
- Return-condition photo set sourced (only if building Return Intelligence — Phase 5)
**Exit criteria:** you could hand this catalog + query set to someone else and they could demo Discovery without you.

### Phase 2 — Discovery agent core (Day 2)
**Goal:** the single highest-value, judge-facing capability works end to end.
- Structured intent extraction via Gemini function calling
- Vector search retrieval wired to the catalog
- Match-quality threshold logic — score ≥0.75 returns normal results, below it explains the gap and shows near-matches (never a bare "no results" page)
- Image-query handling (upload a photo → structured intent → same retrieval path)
- Grounded, SKU-cited match explanations, with an explicit prompt guardrail against describing anything not retrieved
- Every search event logged to Firestore
**Exit criteria:** typing a deliberately vague or misspelled query never returns a dead end — it always returns something plus an explanation, and it's provably grounded (run the adversarial test set, OG-018).

### Phase 3 — Fit-check + Insight agent (Day 3)
**Goal:** the "closed loop" claim becomes real — failed/uncertain moments turn into logged signal.
- Fit-check trigger logic (return-prone category + elevated return rate only — most add-to-cart events skip it entirely)
- SKU-specific clarifying question generation
- Resolution handling and logging
- Insight pipeline: aggregate → cluster by meaning → score in code (never in the LLM) → classify signal type → generate a grounded merchant brief
- On-demand "Generate Insights" endpoint (don't wait for a nightly batch job — you need this to run live in your demo)
**Exit criteria:** running a demo session, then hitting "Generate Insights," produces a brief that traces back to something that actually happened in that session — not a canned example.

### Phase 4 — Frontend + deployment (Day 4)
**Goal:** a real, live URL a judge could open exists.
- Shopper widget (search + image upload + fit-check question UI)
- Demo storefront page hosting the widget
- Merchant dashboard (insight cards, revenue-at-risk badges, "Generate Insights" button)
- Everything deployed to Firebase Hosting + Cloud Run, verified against the live URL (not localhost)
**Exit criteria — this is your go/no-go checkpoint.** If Phase 4 is done and stable, you have a fully submittable product even if you build nothing else. Everything past this point is upside, not requirement.

### Phase 5 — Stretch scenarios (Day 5, only if Phase 4 finished early)

Two tracks, in priority order. **Build 5A before 5B** — 5A extends agents you've already built and tested in Phases 2–3, so it's lower-risk than 5B, which needs new data pipelines (store matrix, return photos) before any code gets written.

#### Phase 5A — Feature extensions (build first)
All six reuse the existing Discovery, Fit-Check, or Insight agent — none require a new agent, a new data source, or a new frontend surface, which is what keeps them cheap relative to 5B.

| Feature | Extends | Ticket(s) | Effort |
|---|---|---|---|
| Iterative refinement — "show me cheaper" / "something bolder" narrows the current result set instead of restarting the search | Discovery agent | OG-048 | 3h |
| Multilingual & voice-first search — shopper searches by voice or in their own language | Discovery agent | OG-049 | 4h |
| Post-purchase fit follow-up — one personalized tip grounded in the actual fit-check answer given, sent after a flagged purchase | Fit-Check agent | OG-050 | 2h |
| Ask-your-data merchant chat — merchant asks a free-form question, Gemini answers via function calling over the event log | Insight agent | OG-051 | 5h |
| Discoverability vs. stock vs. price-gap signal — a fourth signal type for good matches that still didn't convert | Insight agent | OG-052 | 2h |
| Restock-by-date — turns the existing trend_pct into an estimated "restock within N days," not just a flat "restock" flag | Insight agent | OG-053 | 1.5h |

**If you only have time for one:** build **Ask-your-data chat** (OG-051). It's the highest-effort item on this list, but it's also the one that turns the dashboard from static cards into something a judge can actually interact with live — the single best return on stretch time in this plan.

#### Phase 5B — New scenarios (build second, only if 5A is done and stable)
1. **Stockout Rescue** (OG-033 to OG-036) — needs the store stock matrix from Phase 1
2. **Return Intelligence** (OG-037 to OG-039) — build the condition-grading and return-risk scoring as two separate, honestly-labeled signals per the review fix; add the human-confirmation UI before it's demoable

**Decision rule:** if you're not comfortably through Phase 4 by end of Day 4, skip Phase 5 entirely (both tracks) and move to Plan B's talking points for how to present the stretch scope as roadmap rather than live demo. If you're through Phase 4 with only a little slack, do 5A only — it's cheaper and lower-risk than 5B. Don't let stretch scope of either track threaten your working core.

### Phase 6 — Submission assets (Day 6, or Day 5–6 if Phase 5 was skipped)
- Pitch deck (PDF) — problem, solution, architecture, live screenshots, judging-criteria alignment, honest scope/roadmap slide
- 3-minute video: two live scenarios (Discovery is mandatory; pick one more), a freeze-frame for anything not fully live, architecture recap, close on impact
- Final architecture diagram, scope-labeled (what's live vs. planned)
- README with setup instructions and an explicit category statement
- Full end-to-end run-through on deployed URLs, immediately before the deadline

---

## 4. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Vector search setup takes longer than budgeted | Medium | Use Firestore-native vector search for the MVP; Vertex AI Vector Search is explicitly a "stretch," not a dependency |
| Agent mesh (ADK orchestrator) adds debugging overhead late in the week | Medium | Phase 2–3 tickets are written against direct Gemini function-calling; only introduce ADK once the core loop is proven, not before |
| Demo data doesn't look realistic enough for judges | Low–Medium | Phase 1 explicitly budgets time to hand-review the synthetic query set before building on top of it |
| Live demo fails during recording/presentation | Medium | Phase 6 mandates a full run-through on the *deployed* URL, not local, with enough buffer to re-record if something breaks |
| Team over-invests in stretch scope and the core breaks | Medium | Phase 4 is a hard go/no-go gate — stretch work does not start until the core is deployed and verified |

---

## 5. Definition of done (mapped to mandatory submission requirements)

| Requirement | Satisfied by |
|---|---|
| Clear proposal (deck/PDF) | Phase 6 |
| Functional prototype, deployed on Cloud Run/Firebase | Phase 4 exit criteria |
| 3-minute video | Phase 6 |
| Category clearly identified | README + deck (Retail & Commerce) |
| Uses Gemini/Gemma or an agentic platform | Gemini Flash + Pro throughout; ADK if Phase 5 is reached |

---

## 6. Future scope (not ticketed)

These are real product ideas and worth a slide in the deck, but none of them get a ticket this week. Each is a genuine build — new integrations, new UI paradigms, or new hardware assumptions — not an extension of an agent that already exists, so each would compete directly with the Phase 4 go/no-go gate rather than sit cheaply alongside it the way Phase 5A does.

| Idea | What it would add |
|---|---|
| Sustainability framing on Rescue substitutes | Surface the shorter-distance / lower-footprint angle when Stockout Rescue suggests a nearby-store pickup over shipping |
| Bundle / cross-sell signal | Insight agent surfaces co-occurring searches ("shoppers who search X also search Y") as a merchandising suggestion |
| AR try-on | Visual try-on for apparel/footwear before purchase |
| Full catalog-import onboarding | Self-serve flow for a merchant to connect their real Shopify/WooCommerce catalog instead of a seeded demo one |
| In-store kiosk mode | A physical-store variant of the shopper widget for in-aisle use |

Two of these — the sustainability framing and the bundle signal — are cheap enough in isolation that they were flagged as candidates for Phase 5A in review. They're grouped here instead because the team's stretch time this week is better spent on the six Phase 5A tickets that are already scoped and estimated; revisit them first if Phase 5A finishes with time to spare. Mention all five as an explicit "what we'd build next" slide in the deck — this is exactly the kind of honest, scoped roadmap that the Scalability & sustainability judging criterion is looking for, and it costs a slide, not a sprint.

---

*Companion documents: `feasible_plan_v2.md` (lean alternative and fallback plan), `offgrid_tickets.xlsx` (full backlog with effort estimates and dependencies).*
