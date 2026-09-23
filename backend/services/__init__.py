"""Thin, typed wrappers around every external dependency (GCP clients).

Every class here takes a `config.Settings` instance (defaulting to
`get_settings()`), wraps outbound calls with `core.retry`, logs through
`core.logging`, and translates raw SDK exceptions into the
`core.exceptions` hierarchy. No business/application logic lives here —
that belongs in `agents/`, `routers/`, and `scripts/`.
"""
