# OffgridAI

OffgridAI is an AI-powered commerce intelligence platform designed to detect when a shopping journey is about to fail, recover it in real time, and convert failed customer intent into actionable merchant insights.

The project is built around a closed-loop customer experience: understand intent, improve discovery, rescue failed searches or stockouts, guide product fit, analyze returns, and generate business intelligence for merchants.

## Why this project exists

Retail and commerce experiences often fail in three costly ways:

- search and discovery fail because shoppers cannot find the right product
- customers buy the wrong item and return it later
- stockouts and weak recommendations create lost revenue and poor demand visibility

OffgridAI turns these failures into structured, useful signals instead of discarded interactions.

## Core concept

OffgridAI is a platform-agnostic intelligence layer that sits between the customer and a commerce system. It can be used across:

- storefront web experiences
- mobile apps
- messaging channels
- store associate workflows
- merchant dashboards

The system captures shopper intent, performs semantic product discovery, validates fit, handles stockout rescue flows, and then synthesizes business-level insight from the resulting event data.

## Key capabilities

- semantic product discovery and rescue flows
- fit-check guidance for return-prone items
- stockout substitution recommendations
- return intelligence and disposition analysis
- merchant insight generation from high-signal session data
- event-driven architecture for analytics and operational learning

## Architecture overview

The solution is designed around Google AI and Google Cloud services, with a layered architecture consisting of:

- customer-facing surfaces
- a REST API layer
- an orchestrator and specialized AI agents
- data and vector search services
- analytics and insight generation

A high-level architecture diagram is available in `docs/architecture.md`, and the detailed business and technical plan is documented in `docs/solution.md`.

## Repository structure

```text
OffgridAI/
├── LICENSE
├── README.md
├── backend/
│   └── main.py
├── docs/
│   ├── architecture.md
│   ├── backend_implementation_plan.md
│   ├── feasible_plan_v2.md
│   ├── flow_diagram.md
│   ├── implementation_plan.md
│   ├── offgrid_tickets.xlsx
│   ├── solution.md
│   └── ticket_specs.md
├── frontend/
│   └── init.txt
└── .gitignore (if present in repository)
```

## Documentation

This repository includes detailed planning and design documents:

- `docs/solution.md` — product and solution overview
- `docs/architecture.md` — system architecture and data flows
- `docs/implementation_plan.md` — implementation roadmap
- `docs/backend_implementation_plan.md` — backend execution plan
- `docs/ticket_specs.md` — feature and ticket breakdown
- `docs/flow_diagram.md` — flow visualization

## Tech stack

The project plan describes a stack built around:

- Google Gemini / Vertex AI for multimodal reasoning and embeddings
- Google Agent Development Kit for orchestration
- FastAPI for backend APIs
- Firebase for app and real-time data needs
- Firestore for sessions, events, and catalog state
- BigQuery for analytics and BI integration
- Cloud Storage for images and product data

## Project status

This repository currently contains:

- project documentation and planning materials
- the initial backend scaffold
- initial frontend scaffolding

The implementation is in an early stage, with architecture and product direction already defined in the docs.

## Getting started

Clone the repository:

```bash
git clone https://github.com/sanketp27/OffgridAI.git
cd OffgridAI
```

Then review the planning docs before building the application:

```bash
ls
find docs -maxdepth 1 -type f | sort
```

For the implementation roadmap and required system behavior, start with:

- `docs/solution.md`
- `docs/architecture.md`
- `docs/implementation_plan.md`

## License

This project is licensed under the Apache License 2.0. See the `LICENSE` file for details.

## Summary

OffgridAI is a retail intelligence platform that closes the loop between failed customer journeys and merchant action. Instead of treating searches, stockouts, and returns as dead ends, the platform captures them as learning signals that improve product discovery, customer experience, and business decisions.
