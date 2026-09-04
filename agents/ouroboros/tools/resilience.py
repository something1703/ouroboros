"""ADK_AGENTS.md §6's "if a tool errors, record it and continue" checklist item lives
here, not in every prompt — found live: an uncaught `ParallelValidationError` (Parallel
Monitor rejecting a non-HTTPS webhook URL in local dev) propagated all the way through
ADK's function-calling machinery and crashed the entire agent run instead of coming
back as a tool result the LLM could read and react to.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from google.adk.models.google_llm import Gemini
from google.api_core.exceptions import GoogleAPICallError
from google.genai import types

from packages.common.errors import OuroborosError
from packages.common.logging import get_logger

log = get_logger(__name__)


def resilient_model(name: str) -> Gemini:
    """A `Gemini` model handle with a more patient retry policy than ADK's default
    (5 attempts, ~1s-16s backoff -- under 30s total), *and* a hard per-attempt timeout.
    Found live in a real 56-claim CLEAR pass: a burst of `generate_content` calls
    (ClaimTriage's own turns, then the root coordinator's hand-off to CLEAR) tripped
    Vertex AI's per-project-per-region QPM quota for `gemini-3.5-flash`; the default
    retry budget was exhausted before the ~60s quota window rolled over, and — unlike a
    specialist's own per-claim tool failure (see `resilient` above) -- a 429 here
    happens in the model call *outside* any tool's try/except, at the root workflow
    node, so it took down the whole run (docs/DECISIONS.md #063). 8 attempts starting
    at 2s with 2x backoff spans ~150s, comfortably riding out one quota window with
    margin for a second.

    The `timeout` (in `client_kwargs["http_options"]`, not the top-level `retry_options`
    field -- `google_llm.py`'s `api_client` property replaces `http_options` wholesale
    from `client_kwargs`, so anything set there must include `retry_options` itself too,
    or this call's own retry policy is silently dropped) guards a *different* failure
    mode found live retrying the fix above: a follow-up run's 5th `generate_content`
    call logged "Sending out request" and then nothing -- no response, no error, ever
    (confirmed against Cloud Logging minutes later) -- while an isolated call to the
    same model from the same project succeeded in ~2.5s moments later, ruling out a
    genuine model outage. `HttpRetryOptions` only retries a *received* bad status code;
    a request that never gets any response at all isn't something it can catch, so nothing
    was retried and the whole run hung indefinitely. 60s is comfortably above every real
    latency seen so far (a few seconds typical, ~13s worst case) while still turning a
    silent hang into a retryable failure instead of an indefinite one."""
    return Gemini(
        model=name,
        client_kwargs={
            "http_options": types.HttpOptions(
                timeout=60_000,
                retry_options=types.HttpRetryOptions(
                    attempts=8, initial_delay=2.0, max_delay=30.0, exp_base=2.0, jitter=1.0
                ),
            )
        },
    )


def resilient[**P](func: Callable[P, dict[str, object]]) -> Callable[P, dict[str, object]]:
    """Every externally-fallible tool (a real API call, a DB/Firestore write) is
    wrapped so a real failure becomes `{"error": "..."}` in the model's context, never
    a crash — `functools.wraps` preserves the original signature for ADK's schema
    inference (`inspect.signature` follows `__wrapped__` by default).

    Also catches `GoogleAPICallError` (docs/DECISIONS.md #071) — the common base class
    for every real google-cloud-* API failure (`NotFound`, `PermissionDenied`,
    `DeadlineExceeded`, `ResourceExhausted`, ...), not just `OuroborosError`. Found
    live: `firestore_tools.py::write_claim_view` still took down the entire root node
    on a real `google.api_core.exceptions.NotFound` from a live Firestore commit —
    exactly the class of failure this decorator exists to catch per its own docstring
    above ("a real API call, a DB/Firestore write"), just never actually caught outside
    our own `OuroborosError` hierarchy. A genuine programming bug (`TypeError`,
    `AttributeError`, ...) still isn't caught here and still surfaces loudly —
    `test_non_ouroboros_error_still_raises` covers exactly that distinction."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, object]:
        try:
            return func(*args, **kwargs)
        except (OuroborosError, GoogleAPICallError) as exc:
            log.warning("tool_error", tool=func.__name__, error=str(exc))
            return {"error": str(exc)}

    return wrapper
