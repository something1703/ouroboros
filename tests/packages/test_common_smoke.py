from datetime import UTC, datetime

import pytest

from packages.common.clock import FixedClock
from packages.common.errors import BudgetExceeded, NotFound, OuroborosError, SafetyBlocked
from packages.common.ids import new_ulid


def test_domain_errors_derive_from_ouroboros_error() -> None:
    assert issubclass(BudgetExceeded, OuroborosError)
    assert issubclass(NotFound, OuroborosError)
    assert issubclass(SafetyBlocked, OuroborosError)


def test_budget_exceeded_message() -> None:
    err = BudgetExceeded(project_id="demo", spent_usd=10.5, cap_usd=10.0)
    assert "demo" in str(err)


def test_fixed_clock_returns_fixed_time_and_advances() -> None:
    fixed = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FixedClock(fixed)
    assert clock.now() == fixed
    clock.advance(days=1)
    assert clock.now() == datetime(2026, 1, 2, tzinfo=UTC)


def test_fixed_clock_requires_tz_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(datetime(2026, 1, 1))


def test_new_ulid_is_unique_and_sortable_length() -> None:
    a, b = new_ulid(), new_ulid()
    assert a != b
    assert len(a) == 26
