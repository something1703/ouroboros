"""One trivial test per package (AGENTS.md §5 / Phase 1.1 acceptance) — real behaviour is added phase by phase."""

import importlib

import pytest

PACKAGE_NAMES = [
    "packages.ledger",
    "packages.claims",
    "packages.parallel_client",
    "packages.gemini_client",
    "packages.safety",
    "packages.common",
]


@pytest.mark.parametrize("name", PACKAGE_NAMES)
def test_package_imports_cleanly(name: str) -> None:
    module = importlib.import_module(name)
    assert module is not None
