# OffGrid AI — Solution Plan

### Retail & Commerce: Intelligent Customer and Business Experiences

**Hackathon Submission | Google AI + Google Cloud**

---

## 1. Problem Statement

Retailers face three interconnected crises rooted in one missing capability — a real-time signal for what customers actually want:

| Problem | Annual Cost | Root Cause |

|---|---|---|

| Search/discovery failure | $300B (U.S.) | Vocabulary mismatch, zero-result dead ends |

| Wrong-fit returns | $890B (U.S., 2024) | Insufficient pre-purchase guidance |

| Inventory distortion (overstock + stockouts) | $1.7T (global) | No demand signal from failed journeys |

Current AI retail tools are **unidirectional**: they assist the shopper, then discard what happened. OffGrid makes every failure a **closed loop**.

---

## 2. Solution: OffGrid AI

> An embeddable AI intelligence layer that any commerce platform can plug into — detects when a shopping journey is about to fail, rescues it in real time, and turns every failure into a merchant action signal.

### The Rescue Loop (Closed-Loop Flywheel)

```

Customer Intent

      ↓

Semantic Discovery

      ↓

Failure Detected? ──Yes──► AI Rescue (substitute / fit-check / return path)

      │                            ↓

      No                   Outcome Logged

      ↓                            ↓

Purchase            Insight Agent surfaces action

                            ↓

                    Merchant Acts

                            ↓

                    Next customer finds what they need

```

Unlike every AI shopping chatbot, OffGrid **closes the loop** — failed customer intent becomes structured merchant intelligence, not discarded logs.

---

## 3. Five Gemini Agents

| Agent | Responsibility | Model |

|---|---|---|

| **Intent Agent** | Parses text / image / voice → structured intent (category, budget, attributes, use-case, urgency) | Gemini Flash |

| **Discovery + Rescue Agent** | Semantic vector search; never dead-ends; surfaces substitutes; checks local availability | Gemini Flash |

| **Fit-Check Agent** | Triggers only on return-prone SKUs (apparel, footwear, electronics); asks one SKU-specific clarifying question | Gemini Flash |

| **Return Intelligence Agent** | Multimodal: return-item photo → condition + fraud signals + disposition recommendation | Gemini Flash |

| **Insight Agent** | Batch: clusters events by meaning → scores by revenue-at-risk → writes grounded merchant briefs | Gemini Pro |

An **Orchestrator** (Google Agent Development Kit) routes every event to the correct specialist(s) and maintains session context.

**Anti-hallucination rule**: Discovery and Fit-Check agents may only describe products they retrieved from the catalog (cited by SKU ID). The Insight Agent may only state numbers computed in code — never inferred by the LLM.

---

## 4. Three Demo Scenarios

### Scenario 1 — Smart Discovery

*Solves: $300B zero-result search problem*

1. Shopper types a vague query or uploads a photo.

2. Intent Agent extracts structured intent (handles slang, synonyms, images).

3. Discovery Agent performs vector search → returns ranked matches with one-line grounded reasons.

4. If category is return-prone, Fit-Check Agent asks one targeted question.

5. Purchase confirmed → event logged to shared schema.

**Key outcome**: Zero dead ends. Every "no exact match" shows near-matches with an explanation and logs an unmet-demand signal.

---

### Scenario 2 — Stockout Rescue

*Solves: #1 inventory pain point*

1. Shopper requests a specific SKU (e.g., "black running shoes, size 9, under ₹5,000, today").

2. Discovery Agent finds the preferred SKU is out of stock at the local store.

3. Rescue mode: checks substitute SKUs, nearby store availability, fulfilment timing.

4. AI explains the trade-off in plain language ("this runs ₹200 more but ships same day from a nearby store").

5. Customer accepts substitute → logged as `resolution: substitute_accepted`.

**Key outcome**: Revenue saved instead of lost. The stockout event + resolution are signal for the Insight Agent.

---

### Scenario 3 — Return-to-Value

*Solves: $890B returns problem — turns it into an asset*

1. Store associate uploads a photo of a returned item.

2. Return Intelligence Agent reads the image: assesses condition (good / lightly used / damaged), matches against order history, checks for fraud signals (wardrobing, bracketing patterns, policy abuse language).

3. Disposition recommendation generated: "restock" / "refurbish and relist at 15% discount" / "liquidate at 40% markdown".

4. Merchant dashboard updates with recovered inventory value.

**Key outcome**: Every return becomes an optimized business decision, not a blanket approve/reject.

---

### Merchant Dashboard (after all scenarios)

Hit **"Generate Insights"** → Insight Agent processes the session log and outputs 3–5 plain-language briefs, e.g.:

> *"14 shoppers searched for waterproof hiking boots under ₹4,000 this week (↑40% vs. last week) and left without buying — ~₹42,000 in weekly revenue at risk. Consider adding a matching SKU."*

> *"Running shoe size 9 has a 58% fit-check flip rate — shoppers keep switching to 9.5 after one question. Your size chart likely shows incorrect sizing."*

---

## 5. Platform-Agnostic Design

OffGrid is not a Shopify app or a WooCommerce plugin. It is the **intelligence layer between the customer and any commerce system**.

| Surface | Integration method |

|---|---|

| Any web storefront | 5-line JS embed snippet (Firebase CDN) — drops into `<head>` |

| Any backend | REST API (Cloud Run) — POST events, GET insights; language-agnostic |

| Mobile (iOS / Android) | Firebase SDK for native push + real-time session sync |

| Store associate | Progressive Web App (Firebase Hosting) — any browser, no app store |

| Messaging (stretch) | Webhook to same REST API — WhatsApp/Telegram/SMS |

One REST API, one event schema, any platform.

---

## 6. Tech Stack

| Layer | Technology |

|---|---|

| Agent reasoning | Gemini 2.x via Vertex AI (Flash: interactive turns; Pro: batch insights) |

| Agent orchestration | Google Agent Development Kit |

| Retrieval | Gemini embeddings + Firestore vector search → Vertex AI Vector Search (stretch) |

| Compute | Cloud Run (API, agent mesh, insight batch job) |

| App + real-time data | Firebase Hosting, Firestore |

| Auth | Firebase Auth (shopper / associate / merchant roles) |

| Analytics | BigQuery (intent log, SQL-queryable by any BI tool) |

| Object storage | Cloud Storage (shelf images, return photos) |

---

## 7. Data Strategy

| Dataset | Purpose |

|---|---|

| Kaggle Fashion Product Images | Product catalog seed (300–500 SKUs with images + attributes) |

| UCI Online Retail II (~1M transactions) | Customer behavior, product relationships, RFM analysis |

| M5 Walmart Forecasting | Demand + stockout simulation |

| Gemini-generated synthetic data | Vague/misspelled queries, edge-case SKUs, realistic return scenarios |

No proprietary retailer data required — demo is fully reproducible.

---

## 8. Judging Criteria Alignment

| Criterion | Weight | How OffGrid scores |

|---|---|---|

| Technical Merit & Gen AI | 40% | Gemini used in four distinct ways: multimodal intent parsing, structured clarifying dialogue, visual return analysis, unsupervised insight synthesis. Multi-agent ADK orchestration. |

| Problem Alignment & Impact | 25% | Addresses discovery, personalization, conversational shopping, demand signal, inventory, returns, and customer insights in one system. Grounded in $300B + $890B market pain. |

| Innovation & Creativity | 25% | The Rescue Loop (closed-loop flywheel across any platform) vs. the market's unidirectional chatbots. Platform-agnostic embed is the differentiator. |

| UX & Solution Design | 10% | Three purpose-built surfaces: shopper widget, associate PWA, merchant dashboard. |

---

## 9. 3-Minute Video Outline

| Timestamp | Content |

|---|---|

| 0:00–0:25 | Cold open: real zero-result search + "why did I return this" — stat overlays ($300B / $890B) |

| 0:25–1:05 | Live: Scenario 1 — image search → fit check → confident purchase |

| 1:05–1:45 | Live: Scenario 2 — stockout → substitute rescue → customer accepts |

| 1:45–2:20 | Live: Scenario 3 — return photo → AI disposition → merchant dashboard updated |

| 2:20–2:45 | Dashboard: "Generate Insights" → 3 briefs appear with revenue-at-risk numbers |

| 2:45–3:00 | Architecture recap (Gemini + Cloud Run + Firebase), embed snippet shown, scalability note |

---

## 10. Differentiation Summary

| What others build | What OffGrid builds |

|---|---|

| SEARCH → RECOMMEND → BUY | INTENT → DISCOVER → RESCUE → FULFILL → LEARN |

| Single-platform app | Platform-agnostic intelligence layer |

| Discards failed sessions | Turns failures into merchant signals |

| Chatbot with logging | Closed-loop flywheel with structured demand intelligence |

| One user persona | Three personas (shopper + associate + merchant) from one data layer |
