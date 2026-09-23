"""core/retry.py — Shared auto-retry policy for outbound GCP/Vertex AI calls.

The risk register in the backend implementation plan calls out Vertex AI
rate limits during the demo as a Medium/High risk, mitigated by "tenacity
exponential backoff on all Gemini calls." This module is that mitigation,
generalized to every outbound dependency (Firestore, BigQuery, Vertex AI)
so no client in `services/` hand-rolls its own retry loop.

Usage — decorate any sync or async function that makes a single outbound
call:

    from core.retry import retry_gcp_call

    class FirestoreClient:
        @retry_gcp_call(logger=logger)
        async def get_document(self, ...): ...

Tuning comes from `Settings` (`retry_max_attempts`, `retry_initial_wait_seconds`,
`retry_max_wait_seconds`, `retry_jitter_seconds`) so ops can loosen/tighten
retry behavior per-environment via `.env` without a code change.
"""

from __future__ import annotations

from typing import Any, TypeVar

import httpx
from google.api_core import exceptions as gcp_exceptions
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from config import Settings, get_settings

F = TypeVar("F", bound=Any)

# Exceptions worth retrying: transient/rate-limit conditions where a retry
# is likely to succeed. Anything else (PermissionDenied, InvalidArgument,
# NotFound, ...) is a real bug or a real 404 and should fail immediately —
# retrying it would just burn the retry budget masking a genuine error.
RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    gcp_exceptions.ResourceExhausted,  # 429 — quota/rate limit
    gcp_exceptions.TooManyRequests,  # 429
    gcp_exceptions.ServiceUnavailable,  # 503
    gcp_exceptions.InternalServerError,  # 500
    gcp_exceptions.Aborted,  # 409 — concurrent modification, safe to retry
    gcp_exceptions.DeadlineExceeded,  # 504 / client-side timeout
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    ConnectionError,
    TimeoutError,
)


def _before_sleep_log(retry_state: RetryCallState) -> None:
    """tenacity `before_sleep` hook that logs each retry attempt via structlog.

    Deliberately imports `get_logger` lazily to avoid a hard import-time
    dependency between core.retry and core.logging (and the config parsing
    it triggers) for callers that only need the retry decorator.
    """
    from core.logging import get_logger

    logger = get_logger("core.retry")
    outcome = retry_state.outcome
    exc = outcome.exception() if outcome is not None else None
    next_action = retry_state.next_action
    logger.warning(
        "retrying_after_transient_error",
        function=getattr(retry_state.fn, "__qualname__", "unknown"),
        attempt=retry_state.attempt_number,
        wait_seconds=round(next_action.sleep, 2) if next_action else None,
        error_type=type(exc).__name__ if exc else None,
        error_message=str(exc) if exc else None,
    )


def retry_gcp_call(
    *,
    settings: Settings | None = None,
    retryable_exceptions: tuple[type[BaseException], ...] = RETRYABLE_EXCEPTIONS,
    max_attempts: int | None = None,
):
    """Decorator factory: exponential backoff + jitter for a single outbound call.

    Works transparently on both `async def` and `def` functions — tenacity
    detects and awaits coroutine functions automatically.

    Args:
        settings: Defaults to `get_settings()`. Pass explicitly in tests to
            use a fast retry schedule instead of the real one.
        retryable_exceptions: Override the default GCP/network transient-error
            tuple, e.g. to also retry a client-specific exception.
        max_attempts: Override `settings.retry_max_attempts` for this call site.
    """
    settings = settings or get_settings()
    attempts = max_attempts or settings.retry_max_attempts

    return retry(
        reraise=True,
        stop=stop_after_attempt(attempts),
        wait=wait_exponential_jitter(
            initial=settings.retry_initial_wait_seconds,
            max=settings.retry_max_wait_seconds,
            jitter=settings.retry_jitter_seconds,
        ),
        retry=retry_if_exception_type(retryable_exceptions),
        before_sleep=_before_sleep_log,
    )


# Convenience alias: identical policy, distinct name so call sites read
# clearly (e.g. `@retry_gemini_call()` on an embeddings/generate_content
# call vs. `@retry_gcp_call()` on a Firestore write). Kept separate from
# `retry_gcp_call` so Gemini-specific tuning can diverge later without
# touching Firestore/BigQuery call sites.
retry_gemini_call = retry_gcp_call
