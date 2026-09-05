"""The `resilient` decorator: catches OuroborosError into {"error": ...}, never lets it
crash the caller — found live when an uncaught ParallelValidationError (a non-HTTPS
Monitor webhook URL) propagated through ADK's function-calling machinery and killed an
entire agent run instead of surfacing as a tool result."""

from __future__ import annotations

import inspect

import pytest
from google.api_core.exceptions import NotFound as GoogleNotFound

from agents.ouroboros.tools.resilience import resilient
from packages.common.errors import NotFound, OuroborosError


def test_success_passes_through() -> None:
    @resilient
    def ok(x: int) -> dict[str, object]:
        return {"x": x}

    assert ok(5) == {"x": 5}


def test_ouroboros_error_becomes_error_dict_not_a_raise() -> None:
    @resilient
    def fails() -> dict[str, object]:
        raise NotFound("claim", "c1")

    result = fails()
    assert "error" in result
    assert "c1" in result["error"]  # type: ignore[operator]


def test_google_api_call_error_becomes_error_dict_not_a_raise() -> None:
    """A real google-cloud-* API failure (e.g. Firestore's NotFound) is exactly the
    "a real API call, a DB/Firestore write" case this decorator documents — found live,
    it wasn't actually caught until GoogleAPICallError was added alongside
    OuroborosError, and a live Firestore NotFound crashed an entire agent run."""

    @resilient
    def fails() -> dict[str, object]:
        raise GoogleNotFound("database (default) does not exist")

    result = fails()
    assert "error" in result
    assert "database (default) does not exist" in result["error"]  # type: ignore[operator]


def test_non_ouroboros_error_still_raises() -> None:
    """Only our own typed domain errors are treated as "expected, tell the model" —
    a genuine bug (e.g. a TypeError) should still surface loudly, not be silently
    swallowed into a vague error string."""

    @resilient
    def fails() -> dict[str, object]:
        raise ValueError("not a OuroborosError")

    with pytest.raises(ValueError, match="not a OuroborosError"):
        fails()


def test_wraps_preserves_the_real_signature_for_adk_schema_inference() -> None:
    """functools.wraps sets __wrapped__, which inspect.signature follows by default —
    this is what lets ADK's FunctionTool see the real typed parameters instead of
    `(*args, **kwargs)`."""

    @resilient
    def example(a: int, *, b: str = "x") -> dict[str, object]:
        return {"a": a, "b": b}

    sig = inspect.signature(example, eval_str=True)
    assert list(sig.parameters) == ["a", "b"]
    assert sig.parameters["a"].annotation is int


def test_error_is_a_string_in_the_returned_dict() -> None:
    """Not just "any error" — confirm the wrapped function's OuroborosError message
    text actually ends up in the returned dict, since that's what the LLM reads."""

    class _Custom(OuroborosError):
        pass

    @resilient
    def fails() -> dict[str, object]:
        raise _Custom("a specific, readable message")

    result = fails()
    assert result == {"error": "a specific, readable message"}
