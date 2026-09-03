"""build_objective per category (PHASE_04.md §4.2: "unit-tested for each category") and
the exclude_domains/location request-shaping logic in search(), without a real network
call (the Parallel client construction itself is monkeypatched).
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from config.parallel import DEFAULT_EXCLUDE_DOMAINS_LEGAL
from packages.claims.enums import ClaimCategory
from packages.parallel_client import search as search_module
from packages.parallel_client.search import build_objective, search

_ALL_CATEGORIES = list(ClaimCategory)


@pytest.mark.parametrize("category", _ALL_CATEGORIES)
def test_build_objective_every_category_returns_objective_and_queries(
    category: ClaimCategory,
) -> None:
    objective, queries = build_objective(category, "Test Entity", ["us", "gb"])
    assert "Test Entity" in objective
    assert 1 <= len(queries) <= 3
    for query in queries:
        assert "Test Entity" in query


def test_build_objective_includes_jurisdiction_hint_text() -> None:
    objective, _ = build_objective(ClaimCategory.MUSIC, "Some Song", ["gb"])
    assert "PRS for Music" in objective


def test_build_objective_unknown_jurisdiction_is_silently_skipped() -> None:
    # Should not raise even though "zz" has no entry in config/jurisdictions.yaml.
    objective, _queries = build_objective(ClaimCategory.EVENT, "Some Event", ["zz"])
    assert "Some Event" in objective


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    client = MagicMock()
    client.search.return_value = MagicMock(
        results=[], search_id="search_test", session_id="session_test"
    )
    monkeypatch.setattr(search_module, "get_client", lambda: client)
    return client


def test_search_legal_category_defaults_exclude_domains(fake_client: MagicMock) -> None:
    search("objective", ["q1"], category=ClaimCategory.BRAND)
    _, kwargs = fake_client.search.call_args
    assert kwargs["advanced_settings"]["source_policy"]["exclude_domains"] == (
        DEFAULT_EXCLUDE_DOMAINS_LEGAL
    )


def test_search_factual_category_has_no_default_exclude_domains(fake_client: MagicMock) -> None:
    search("objective", ["q1"], category=ClaimCategory.EVENT)
    _, kwargs = fake_client.search.call_args
    assert "source_policy" not in kwargs["advanced_settings"]


def test_search_explicit_exclude_domains_overrides_default(fake_client: MagicMock) -> None:
    search("objective", ["q1"], category=ClaimCategory.BRAND, exclude_domains=["example.com"])
    _, kwargs = fake_client.search.call_args
    assert kwargs["advanced_settings"]["source_policy"]["exclude_domains"] == ["example.com"]


def test_search_unsupported_location_is_omitted(fake_client: MagicMock) -> None:
    search("objective", ["q1"], location="zz")
    _, kwargs = fake_client.search.call_args
    assert "location" not in kwargs["advanced_settings"]


def test_search_supported_location_is_set(fake_client: MagicMock) -> None:
    search("objective", ["q1"], location="gb")
    _, kwargs = fake_client.search.call_args
    assert kwargs["advanced_settings"]["location"] == "gb"


def test_search_never_sets_include_domains(fake_client: MagicMock) -> None:
    """PHASE_04.md §4.2: "a test asserting include_domains is never set unless
    explicitly passed" — search() has no parameter for it at all, so this is
    trivially true; asserted here so a future signature change can't silently add one
    without this test catching it."""
    search("objective", ["q1"], category=ClaimCategory.BRAND, exclude_domains=["example.com"])
    _, kwargs = fake_client.search.call_args
    source_policy = kwargs["advanced_settings"].get("source_policy", {})
    assert "include_domains" not in source_policy
    assert "include_domains" not in inspect.signature(search).parameters
