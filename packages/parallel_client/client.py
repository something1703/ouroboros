"""Single lazily-constructed `Parallel` client, the retry wrapper every other module in
this package calls through, and structured call logging. See PARALLEL_INTEGRATION.md
§1, §6 and docs/vendor/parallel/README.md (verified real SDK surface).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from functools import cache

import parallel
from parallel import Parallel

from packages.common.errors import ParallelError, ParallelValidationError
from packages.common.logging import get_logger

log = get_logger(__name__)

# PARALLEL_INTEGRATION.md §6: retry 429/5xx/timeout 3x with backoff 1s, 4s, 16s;
# a 4xx validation error never retries.
_RETRY_BACKOFF_S: tuple[int, ...] = (1, 4, 16)
_RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    parallel.RateLimitError,
    parallel.InternalServerError,
    parallel.APITimeoutError,
    parallel.APIConnectionError,
)


@cache
def get_client() -> Parallel:
    from packages.common.secrets import get_secret

    return Parallel(api_key=get_secret("PARALLEL_API_KEY"), timeout=60)


def env_metadata(**extra: str) -> dict[str, str]:
    """Metadata attached to every Task/Monitor call (the only two Parallel APIs that
    accept it) so webhooks and the Parallel dashboard can be traced back to us. Every
    value here is a plain string; callers whose SDK param is typed wider
    (`dict[str, str | float | bool]`, e.g. Task) can pass this as-is — dict's value-type
    invariance just needs an explicit wider-typed copy at the call site."""
    return {"env": os.environ.get("OUROBOROS_ENV", "dev"), **extra}


def call[T](
    fn: Callable[[], T],
    *,
    api: str,
    sku: str,
    claim_id: str | None = None,
    retryable_errors: tuple[type[Exception], ...] = _RETRYABLE_ERRORS,
    status_error: type[Exception] = parallel.APIStatusError,
) -> T:
    """Run `fn()` — a zero-arg closure over one real SDK call — with the retry/logging
    policy every wrapper in this package shares. `fn` must be idempotent: it may run
    up to 4 times.

    `retryable_errors`/`status_error` default to the `parallel` SDK's own exception
    types; `responses.py` passes the `openai` SDK's equivalents instead (Responses is
    called via `openai`, pointed at Parallel's base URL — the two SDKs are both
    stainless-generated with an identical exception hierarchy shape, but distinct
    classes, so `except`ing one never catches the other)."""
    last_exc: Exception | None = None
    for attempt, backoff in enumerate((0, *_RETRY_BACKOFF_S)):
        if backoff:
            time.sleep(backoff)
        start = time.monotonic()
        try:
            result = fn()
        except retryable_errors as exc:
            last_exc = exc
            log.warning(
                "parallel_call_retrying",
                api=api,
                sku=sku,
                claim_id=claim_id,
                attempt=attempt,
                error=str(exc),
            )
            continue
        except status_error as exc:
            log.error("parallel_call_rejected", api=api, sku=sku, claim_id=claim_id, error=str(exc))
            raise ParallelValidationError(f"{api} rejected: {exc}") from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        warnings = getattr(result, "warnings", None) or []
        if warnings:
            log.warning(
                "parallel_call_warnings",
                api=api,
                sku=sku,
                claim_id=claim_id,
                warnings=[w.message for w in warnings],
            )
        log.info("parallel_call", api=api, sku=sku, claim_id=claim_id, latency_ms=latency_ms)
        return result

    log.error("parallel_call_exhausted", api=api, sku=sku, claim_id=claim_id, error=str(last_exc))
    raise ParallelError(f"{api} failed after retries: {last_exc}") from last_exc
