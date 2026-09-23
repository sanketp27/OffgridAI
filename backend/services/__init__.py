"""Infrastructure-facing service wrappers.

Each service wraps exactly one external system (Firestore, Vertex AI
Embeddings, Cloud Storage, BigQuery, the web) behind a small, typed,
async-first interface. Agents and routers depend on these interfaces —
never on the raw Google Cloud SDK clients directly — so they stay mockable
in unit tests and swappable if the backing implementation changes.
"""
