"""core/exceptions.py — Shared exception hierarchy + traceback utilities.

Two things live here:

1. A small, typed exception hierarchy (`OffGridError` and friends) that
   every `services/*` client raises instead of letting raw GCP SDK
   exceptions leak upward. Callers (routers, agents) can catch one
   family (`DependencyError`) instead of importing
   `google.api_core.exceptions` everywhere.

2. Traceback-capture helpers (`format_traceback`, `capture_exception`,
   `error_boundary`) used by every client to log full tracebacks in a
   structured, Cloud-Logging-friendly way before re-raising, so a failure
   three layers down is never silently swallowed or logged as a bare
   one-line message.
"""

from __future__ import annotations

import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

# structlog's BoundLogger is duck-typed (it has .error(), .warning(), ...),
# so we type against `Any` here rather than importing structlog just for a
# type hint and risking a circular import with core.logging.
Logger = Any


class OffGridError(Exception):
    """Base class for every intentionally-raised error in this codebase.

    Attributes:
        message: Human-readable summary (also `str(exc)`).
        code: Short, stable machine-readable identifier (e.g.
            "firestore_unavailable"), suitable for API error bodies and
            log filtering. Defaults to the exception's class name.
        context: Arbitrary structured metadata attached at raise time
            (document id, sku_id, session_id, retry count, ...).
        cause: The original exception this one was translated from, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        context: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or type(self).__name__
        self.context = context or {}
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause

    def to_dict(self) -> dict[str, Any]:
        """Safe, JSON-serializable representation for API error responses.

        Deliberately excludes tracebacks / internal exception reprs — use
        `capture_exception` for the full internal log record.
        """
        return {"error": self.code, "message": self.message, "context": self.context}

    def __repr__(self) -> str:  # pragma: no cover - convenience only
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r}, context={self.context!r})"


class ConfigurationError(OffGridError):
    """Missing or invalid configuration (bad/missing env var, unset secret, ...)."""


class DependencyError(OffGridError):
    """Base class for failures talking to an external system (GCP or otherwise).

    Subclassed per-dependency so callers can catch narrowly
    (`except FirestoreError`) or broadly (`except DependencyError`).
    """


class FirestoreError(DependencyError):
    """Firestore read/write/query failure."""


class VectorSearchError(DependencyError):
    """Vector similarity search failure (Firestore-native or Vertex AI Vector Search)."""


class GeminiError(DependencyError):
    """Gemini chat/generation call failure."""


class EmbeddingError(DependencyError):
    """Gemini embeddings call failure."""


class BigQueryError(DependencyError):
    """BigQuery insert/query failure."""


class NotFoundError(OffGridError):
    """A requested resource (document, SKU, session, ...) does not exist."""


class DataValidationError(OffGridError):
    """Data failed validation *after* successfully round-tripping a dependency.

    (Request/response schema validation is handled by Pydantic itself;
    this is for validation that happens deeper in a client, e.g. a
    Firestore document missing an expected field.)
    """


def format_traceback(exc: BaseException) -> str:
    """Render a full traceback for `exc` as a single string."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def capture_exception(
    logger: Logger,
    exc: BaseException,
    *,
    event: str = "unhandled_exception",
    **context: Any,
) -> None:
    """Log `exc` with a full structured traceback, then let the caller decide what to do next.

    This never raises and never swallows — it only logs. Call it at the
    point an exception is caught, immediately before translating it into
    an `OffGridError` subclass and re-raising (see `error_boundary`
    below for the common case of that pattern).

    Example:
        >>> try:
        ...     await client.get_document("catalog", sku_id)
        ... except Exception as exc:
        ...     capture_exception(logger, exc, event="firestore_get_failed", sku_id=sku_id)
        ...     raise FirestoreError("failed to load SKU", context={"sku_id": sku_id}, cause=exc) from exc
    """
    logger.error(
        event,
        error_type=type(exc).__name__,
        error_message=str(exc),
        traceback=format_traceback(exc),
        **context,
    )


@contextmanager
def error_boundary(
    logger: Logger,
    *,
    wrap: type[OffGridError],
    event: str,
    message: str,
    **context: Any,
) -> Iterator[None]:
    """Context manager that logs + translates any exception raised inside it.

    Any `OffGridError` raised inside the block passes through unchanged
    (it's already been classified by an inner layer). Any other exception
    is logged with a full traceback via `capture_exception` and re-raised
    as `wrap(message, context=context, cause=exc)`.

    Example:
        >>> with error_boundary(logger, wrap=FirestoreError, event="firestore_set_failed",
        ...                      message="failed to write SKU", sku_id=sku_id):
        ...     await collection.document(sku_id).set(data)
    """
    try:
        yield
    except OffGridError:
        raise
    except Exception as exc:
        capture_exception(logger, exc, event=event, **context)
        raise wrap(message, context=context, cause=exc) from exc
