"""Retry/error-mapping policy in packages.parallel_client.client.call
(PARALLEL_INTEGRATION.md §6), exercised with fake exceptions — no real network calls,
`time.sleep` patched out so the backoff schedule doesn't actually wait.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import parallel
import pytest

from packages.common.errors import ParallelError, ParallelValidationError
from packages.parallel_client import client as client_module
from packages.parallel_client.client import call


class _FakeRetryable(Exception):
    pass


class _FakeStatusError(Exception):
    pass


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)
    yield


def test_call_succeeds_first_try() -> None:
    result = call(lambda: "ok", api="test", sku="test.sku")
    assert result == "ok"


def test_call_retries_then_succeeds() -> None:
    attempts = {"n": 0}

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _FakeRetryable("try again")
        return "ok"

    result = call(
        flaky,
        api="test",
        sku="test.sku",
        retryable_errors=(_FakeRetryable,),
        status_error=_FakeStatusError,
    )
    assert result == "ok"
    assert attempts["n"] == 3


def test_call_exhausts_retries_and_raises_parallel_error() -> None:
    def always_fails() -> str:
        raise _FakeRetryable("still failing")

    with pytest.raises(ParallelError):
        call(
            always_fails,
            api="test",
            sku="test.sku",
            retryable_errors=(_FakeRetryable,),
            status_error=_FakeStatusError,
        )


def test_call_status_error_never_retries() -> None:
    attempts = {"n": 0}

    def rejected() -> str:
        attempts["n"] += 1
        raise _FakeStatusError("bad request")

    with pytest.raises(ParallelValidationError):
        call(
            rejected,
            api="test",
            sku="test.sku",
            retryable_errors=(_FakeRetryable,),
            status_error=_FakeStatusError,
        )
    assert attempts["n"] == 1


def _real_internal_server_error(message: str) -> parallel.InternalServerError:
    request = httpx.Request("POST", "https://api.parallel.ai/v1/tasks/runs")
    response = httpx.Response(500, request=request)
    return parallel.InternalServerError(message, response=response, body=None)


def test_call_retries_the_real_parallel_500_by_default() -> None:
    # PHASE_09.md §9.5: the existing retry tests above all pass an explicit
    # `retryable_errors=(_FakeRetryable,)` override -- none of them exercise the
    # *real* default `_RETRYABLE_ERRORS` tuple `run()`/`search()` actually use in
    # production. This one calls `call()` with no override at all, using a real
    # `parallel.InternalServerError` (the SDK's real 500 type), confirming the
    # default policy retries it (not just that a fake stand-in class can be retried).
    attempts = {"n": 0}

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _real_internal_server_error("real 500, try again")
        return "ok"

    result = call(flaky, api="test", sku="test.sku")
    assert result == "ok"
    assert attempts["n"] == 3


def test_call_exhausts_real_parallel_500_and_raises_parallel_error() -> None:
    def always_500() -> str:
        raise _real_internal_server_error("real 500, still failing")

    with pytest.raises(ParallelError):
        call(always_500, api="test", sku="test.sku")


def test_call_logs_warnings_without_raising() -> None:
    class _Result:
        def __init__(self) -> None:
            self.warnings = [type("W", (), {"message": "heads up"})()]

    result = call(lambda: _Result(), api="test", sku="test.sku")
    assert isinstance(result, _Result)
