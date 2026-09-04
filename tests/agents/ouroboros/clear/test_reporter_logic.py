"""Pure-logic coverage for agents/ouroboros/clear/reporter.py's release-date handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agents.ouroboros.clear.reporter import _days_to_release


def test_none_release_date_defaults_to_far_off() -> None:
    assert _days_to_release(None) == 999


def test_non_string_release_date_defaults_to_far_off() -> None:
    assert _days_to_release(12345) == 999


def test_empty_string_defaults_to_far_off() -> None:
    assert _days_to_release("") == 999


def test_future_date_computes_positive_days() -> None:
    future = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
    days = _days_to_release(future)
    assert 28 <= days <= 31


def test_past_date_clamps_to_zero() -> None:
    past = (datetime.now(UTC).date() - timedelta(days=10)).isoformat()
    assert _days_to_release(past) == 0


def test_datetime_style_iso_string_is_accepted() -> None:
    future = (datetime.now(UTC).date() + timedelta(days=5)).isoformat() + "T00:00:00Z"
    days = _days_to_release(future)
    assert 3 <= days <= 6
