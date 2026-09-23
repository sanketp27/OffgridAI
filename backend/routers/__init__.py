"""FastAPI routers — one module per resource area (Implementation Plan §10.1).

Each router owns its own request/response Pydantic schemas (distinct from
the Firestore document models in `models/`) and depends on
`dependencies.verify_token` / `dependencies.require_role` for auth, and
`dependencies.get_orchestrator` / `get_db` / etc. for service access.
"""
