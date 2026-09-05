"""Pure-logic coverage for release-date handling: `reporter.py`'s own ISO-string
parsing (`_release_date_from_state`) and the shared `days_to_release` policy
(`config/parallel.py`, also used by `dashboard_api`'s coil-tightening job)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agents.ouroboros.clear.reporter import _release_date_from_state
from config.parallel import days_to_release


def test_none_release_date_defaults_to_far_off() -> None:
    assert days_to_release(_release_date_from_state(None)) == 999


def test_non_string_release_date_defaults_to_far_off() -> None:
    assert days_to_release(_release_date_from_state(12345)) == 999


def test_empty_string_defaults_to_far_off() -> None:
    assert days_to_release(_release_date_from_state("")) == 999


def test_future_date_computes_positive_days() -> None:
    future = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
    days = days_to_release(_release_date_from_state(future))
    assert 28 <= days <= 31


def test_past_date_clamps_to_zero() -> None:
    past = (datetime.now(UTC).date() - timedelta(days=10)).isoformat()
    assert days_to_release(_release_date_from_state(past)) == 0


def test_datetime_style_iso_string_is_accepted() -> None:
    future = (datetime.now(UTC).date() + timedelta(days=5)).isoformat() + "T00:00:00Z"
    days = days_to_release(_release_date_from_state(future))
    assert 3 <= days <= 6


def test_days_to_release_accepts_a_real_date_directly() -> None:
    """`dashboard_api`'s coil-tightening job (PHASE_07.md §7.3) already has a real
    `date` from `ProjectRepo`/`MonitorRepo.list_all_active` — no ISO-string parsing
    step needed for that caller."""
    future = datetime.now(UTC).date() + timedelta(days=10)
    assert 8 <= days_to_release(future) <= 10
