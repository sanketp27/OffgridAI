# OffGrid Core — 2nd Feasible Plan (Plan B: Lean Build)

**Retail & Commerce: Intelligent Customer and Business Experiences**
Hackathon Submission | Google AI + Google Cloud

---

## 1. When to use this plan instead of Plan A

Use Plan B if any of these are true:
- Your team is 1–2 people, not 2–4
- You have 3–4 days, not 6
- You're following `implementation_plan.md` (Plan A) and reach the **end of Day 4 without a stable, deployed core** — in that case, stop building new scope and execute Plan B's submission path with what's already working

Plan B is **not a different product** — it's a strict subset of Plan A's data model and event schema. Nothing you build here is thrown away if you later have time to add Plan A's stretch scope; you'd be adding tickets, not re-architecting.

---

## 2. What's cut, and why each cut is safe

| Cut from Plan A | Why it's safe to cut |
|---|---|
| Return Intelligence Agent (Scenario 3) | Solves a real problem ($890B returns) but is the least feasible piece to demo convincingly in limited time, and was the source of the fraud-claim issue in review — cutting it removes that risk entirely |
| Stockout Rescue Agent (Scenario 2) | Needs synthetic multi-store inventory data you don't otherwise need; Discovery + Insight alone already carries the core differentiation |
| Google ADK orchestrator / multi-agent mesh | A single Cloud Run service calling Gemini directly via function calling does the same job with far less integration surface to debug under time pressure |
| BigQuery mirror | Firestore aggregation is enough to demo the Insight pipeline; BigQuery is a one-line "production would add this" note, not a build item |
| Associate PWA, mobile SDK, messaging webhooks, Shopify/WooCommerce embeds | None of these are demoable without also building the surface that would call them; keep them as an architecture/roadmap slide, not a build task |

**What is *not* cut, because it's the actual differentiator:** the closed loop itself. Discovery and Fit-Check still log every event; Insight still turns those events into a grounded merchant brief. If you cut this, you're back to "just a chatbot," which is the exact positioning trap the architecture review flagged.

---

## 3. Simplified architecture

- **One Cloud Run service** (not an agent mesh) exposing two endpoints: `/search` and `/insights`
- **Two logical agents, no orchestrator layer between them and the API:**
  - **Discovery + Fit copilot** — a single Gemini Flash agent using function calling for structured intent extraction, vector retrieval, match-quality routing, and (for return-prone categories) the fit-check question — all in one conversational flow, not separate agent hops
  - **Insight agent** — Gemini Pro, same pipeline as Plan A: aggregate → cluster → score in code → classify → grounded brief
- **Firestore only** for catalog, vector index, events, and insights — no BigQuery, no Cloud Storage (no return photos to store)
- **Two frontend surfaces** — shopper widget + merchant dashboard — no associate PWA

This is a strict subset of the diagram in `architecture.md`: remove the Return Intelligence Agent, the Stockout Rescue branch, the Orchestrator box, and everything under "Business Surfaces" except the Merchant Dashboard. Everything that remains is unchanged.

---

## 4. Compressed timeline (3–4 days)

| Day | Focus |
|---|---|
| Day 1 | Setup (Phase 0) + data prep (Phase 1, core only — skip store matrix and return photos) |
| Day 2 | Discovery + Fit-Check agent, fully working and logging events |
| Day 3 | Insight pipeline + both frontend surfaces, deployed |
| Day 4 (if available) | Deck, video, polish — or fold into Day 3 evening if the timeline is truly 3 days |

**Estimated effort:** ~89 hours of ticket work (see `offgrid_tickets.xlsx`, filter the Plan column to "Both"). Divided across a 2-person team working full days, that's roughly 3 days each in parallel — consistent with the table above.

---

## 5. How to still score well with reduced scope

The judging weights reward *meaningful* Gen AI use and *innovation*, not headcount of agents. Plan B still has real answers for both:

- **Technical merit (40%):** Gemini is still doing three distinct jobs — multimodal intent parsing, grounded conversational clarification, and unsupervised synthesis of business insight from raw logs. That's the same substance as Plan A, just without the extra orchestration layer.
- **Innovation (25%):** the closed-loop pitch — *failed customer intent becomes merchant intelligence instead of being discarded* — is fully intact. That's the differentiator, and it doesn't depend on having five agents.
- **Problem alignment (25%):** still grounded in the same $300B search-abandonment and $890B returns figures; you're solving the first one fully and demonstrating the mechanism (fit-check → logged signal) that would extend to the second.
- **Roadmap slide earns credit without needing to be built:** present Stockout Rescue and Return Intelligence explicitly as "designed, not yet built" with one diagram each — this is honest and still demonstrates the scalability judges are scoring, without the risk of a live demo failure on something you didn't have time to harden.

**One framing line worth using directly in the pitch:** *"We scoped deliberately to ship one complete loop rather than three partial ones — the architecture is designed to extend to stockout and returns without changing the core data model."* That sentence turns the cut into a demonstrated engineering judgment call rather than an admission of running out of time.

---

## 6. Upgrade path

If you're ahead of schedule on Day 3, the next-highest-value additions in order are:
1. Stockout Rescue (OG-033 to OG-036) — reuses the same Discovery agent, adds one branch
2. The honest "architecture supports X platforms" slide with one platform actually wired beyond the demo storefront (e.g., a second embed target)
3. Return Intelligence — only attempt this last, and only with the review's fix already applied (condition from photo, risk from order history, human confirmation required)

Do not start any of these until the Plan B core (Sections 3–4 above) is deployed and verified end-to-end.

---

*Companion documents: `implementation_plan.md` (full build, Plan A), `offgrid_tickets.xlsx` (filter the Plan column to "Both" for this plan's exact scope).*
