"""Injectable clock so tests never depend on wall-clock time. UTC everywhere."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Anything that can tell you the current UTC time."""

    def now(self) -> datetime: ...


class SystemClock:
    """The real clock. Use this in production code."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """A clock that always returns the same instant. Use this in tests."""

    def __init__(self, fixed: datetime) -> None:
        if fixed.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed

    def advance(self, **timedelta_kwargs: float) -> None:
        from datetime import timedelta

        self._fixed = self._fixed + timedelta(**timedelta_kwargs)


DEFAULT_CLOCK: Clock = SystemClock()
