"""Typed, metered wrapper around the Parallel Web Systems API. No other code imports
parallel/openai (Parallel-pointed) directly — see PARALLEL_INTEGRATION.md §1.
"""

from __future__ import annotations

from packages.parallel_client import (
    basis,
    entity,
    extract,
    memory,
    monitor,
    responses,
    search,
    task,
    webhooks,
)
from packages.parallel_client import cost as cost

__all__ = [
    "basis",
    "cost",
    "entity",
    "extract",
    "memory",
    "monitor",
    "responses",
    "search",
    "task",
    "webhooks",
]
