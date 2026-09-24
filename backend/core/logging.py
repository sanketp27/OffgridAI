"""core/logging.py — Structured logging setup (structlog), Cloud Logging compatible.

Cloud Run/Cloud Logging automatically parses JSON written to stdout and
promotes a `severity` field to the log entry's severity, and a `message`
field to the entry's summary text, when present. This module configures
`structlog` to always emit exactly that shape in `staging`/`production`,
and a human-readable colored console renderer in `local` dev.

Usage (call once, at process startup — e.g. top of `main.py`):

    from core.logging import configure_logging, get_logger
    configure_logging()
    logger = get_logger(__name__)
    logger.info("service_started", port=8080)

Per-request/session correlation:

    from core.logging import bind_context, clear_context
    bind_context(request_id=request_id, session_id=session_id, store_id=store_id)
    ...  # every log call on this task now automatically includes those fields
    clear_context()  # e.g. in FastAPI middleware, after the response is sent

Exceptions: prefer `core.exceptions.capture_exception` / `error_boundary`,
which use this module's loggers and always include a full structured
traceback (`structlog.processors.dict_tracebacks`) rather than a bare
string — this keeps stack frames queryable as JSON fields in Cloud
Logging instead of buried in an unstructured blob.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any, cast

import structlog

from config import Settings, get_settings

_CONFIGURED = False


def configure_logging(settings: Settings | None = None) -> None:
    """Configure structlog (and the stdlib logging root) for this process.

    Idempotent — safe to call multiple times (e.g. once in `main.py`, once
    again defensively in a Cloud Run Job entrypoint); only the first call
    takes effect.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = settings or get_settings()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level.upper(),
    )

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        # Renders exc_info into a nested, JSON-safe dict of frames instead
        # of a flat string — queryable in Cloud Logging, not just readable.
        structlog.processors.dict_tracebacks,
        _add_service_context(settings),
    ]

    if settings.log_json:
        processors: list[structlog.typing.Processor] = [
            *shared_processors,
            _rename_event_to_message,
            _level_to_severity,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level.upper())
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger. Call `configure_logging()` first (idempotent)."""
    if not _CONFIGURED:
        configure_logging()
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


def bind_context(**kwargs: Any) -> None:
    """Bind fields (request_id, session_id, store_id, ...) to every log call on this task/thread."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context fields. Call at the end of each request/job."""
    structlog.contextvars.clear_contextvars()


def _add_service_context(settings: Settings) -> structlog.typing.Processor:
    """Stamp every log entry with the service name + environment."""

    def processor(
        _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        event_dict.setdefault("service", settings.service_name)
        event_dict.setdefault("env", settings.env)
        return event_dict

    return processor


def _rename_event_to_message(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Cloud Logging shows the `message` field as the log's summary text."""
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


# Cloud Logging severities, in ascending order. structlog/stdlib level names
# already line up except WARN -> WARNING and CRITICAL -> CRITICAL (no-op),
# so this is mostly a pass-through kept explicit for clarity.
_SEVERITY_MAP = {
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARNING",
    "warn": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL",
    "exception": "ERROR",
}


def _level_to_severity(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    level = str(event_dict.pop("level", "info")).lower()
    event_dict["severity"] = _SEVERITY_MAP.get(level, "DEFAULT")
    return event_dict
