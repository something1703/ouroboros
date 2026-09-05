"""entity.search()'s match_limit floor — found live in Phase 5: the real API rejects
match_limit < 5 with a 422 (docs/vendor/parallel/README.md's documented 5-1000 range).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from packages.parallel_client import entity as entity_module
from packages.parallel_client.entity import search


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    client = MagicMock()
    client.beta.findall.entity_search.return_value = MagicMock(entities=[])
    monkeypatch.setattr(entity_module, "get_client", lambda: client)
    return client


def test_low_limit_is_raised_to_the_api_minimum(fake_client: MagicMock) -> None:
    search("objective", "companies", limit=3)
    _, kwargs = fake_client.beta.findall.entity_search.call_args
    assert kwargs["match_limit"] == 5


def test_limit_above_minimum_is_passed_through(fake_client: MagicMock) -> None:
    search("objective", "companies", limit=25)
    _, kwargs = fake_client.beta.findall.entity_search.call_args
    assert kwargs["match_limit"] == 25
