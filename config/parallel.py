"""Parallel API modes/processors per use case, cost caps, and geo-targeting policy.

The single source of truth for anything `packages/parallel_client/` needs to decide
without an LLM in the loop. See `PARALLEL_INTEGRATION.md` for the full contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

import yaml

_JURISDICTIONS_PATH = Path(__file__).parent / "jurisdictions.yaml"


def _load_jurisdictions() -> dict[str, dict[str, object]]:
    with _JURISDICTIONS_PATH.open() as f:
        return yaml.safe_load(f) or {}


JURISDICTIONS: Final[dict[str, dict[str, object]]] = _load_jurisdictions()

# --- Geo-targeting -----------------------------------------------------------
#
# Parallel's Search API docs (checked 2026-08-31) state: "only a subset of
# countries are currently supported; unsupported or invalid values are
# ignored with a warning" — but do not publish the full enumerated list.
# This set is Ouroboros's best-effort curation (ISO 3166-1 alpha-2, lowercase;
# note 'gb' not 'uk'). Passing a code outside this set is not dangerous —
# Parallel ignores it and logs a warning rather than erroring — but omitting
# `location` and relying on `objective_hint` wording is the honest fallback.
# Refine this list from real Search response warnings once Phase 4 is live
# (see docs/DECISIONS.md).
SUPPORTED_LOCATIONS: Final[frozenset[str]] = frozenset(
    {
        "us",
        "gb",
        "de",
        "fr",
        "it",
        "es",
        "nl",
        "se",
        "no",
        "dk",
        "fi",
        "pl",
        "ie",
        "pt",
        "at",
        "ch",
        "be",
        "gr",
        "cz",
        "ro",
        "jp",
        "kr",
        "in",
        "au",
        "nz",
        "sg",
        "hk",
        "tw",
        "id",
        "th",
        "vn",
        "ph",
        "my",
        "ca",
        "mx",
        "br",
        "ar",
        "cl",
        "co",
        "za",
        "ae",
        "sa",
        "il",
        "tr",
    }
)
assert "uk" not in SUPPORTED_LOCATIONS, "use 'gb', Parallel does not recognize 'uk'"

# --- Search --------------------------------------------------------------
# Verified live against POST https://api.parallel.ai/v1/search on 2026-09-03
# (mode='fast', real 200 response — see docs/DECISIONS.md #018). Do not
# confuse with /v1beta/search, an unrelated beta endpoint with a different
# mode enum ('agentic'/'fast'/'one-shot') — that path was a mistaken guess
# during verification, not part of this plan.
SearchMode = Literal["turbo", "fast", "basic", "advanced"]
SEARCH_MODE_DEFAULT: Final[SearchMode] = "fast"

# Applied by default for legal-category searches only (noise, not signal).
# Factual (TRUE CUT) searches pass none by default.
DEFAULT_EXCLUDE_DOMAINS_LEGAL: Final[list[str]] = [
    "pinterest.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
]

# --- Task ------------------------------------------------------------------
TaskProcessor = Literal[
    "lite",
    "lite-fast",
    "base",
    "base-fast",
    "core",
    "core-fast",
    "core2x",
    "core2x-fast",
    "pro",
    "pro-fast",
]
TASK_PROCESSOR_DEFAULT: Final[TaskProcessor] = "core-fast"
TASK_PROCESSOR_ESCALATION: Final[TaskProcessor] = "pro"

# Never run these in the pipeline (cost). Enforced in packages/parallel_client/task.py.
FORBIDDEN_TASK_PROCESSOR_PREFIXES: Final[tuple[str, ...]] = ("ultra",)
FORBIDDEN_MONITOR_PROCESSORS: Final[frozenset[str]] = frozenset({"base"})

TASK_MAX_INPUT_CHARS: Final[int] = 4_000
TASK_SPEC_MAX_CHARS: Final[int] = 15_000
TASK_SPEC_PLUS_INPUT_MAX_CHARS: Final[int] = 25_000
TASK_DEFAULT_TIMEOUT_S: Final[int] = 600

# --- Responses ---------------------------------------------------------------
ResponsesEffort = Literal["low", "medium", "high"]
RESPONSES_EFFORT_DEFAULT: Final[ResponsesEffort] = "medium"

# --- Monitor -----------------------------------------------------------------
MonitorFrequency = Literal["1h", "1d", "1w"]
MAX_MONITORS_PER_PROJECT: Final[int] = 40
MAX_EVENT_STREAM_MONITORS_PER_PROJECT: Final[int] = 15
MIN_REVERIFY_COOLDOWN_HOURS: Final[int] = 6


def frequency_for(days_to_release: int) -> MonitorFrequency:
    """Coil-tightening policy: cadence increases as release day approaches."""
    if days_to_release > 60:
        return "1w"
    if days_to_release > 7:
        return "1d"
    return "1h"


# --- Cost --------------------------------------------------------------------
PROJECT_BUDGET_USD_DEFAULT: Final[float] = 10.0

# --- Pricing table (USD), hard-coded from Parallel pricing, checked 2026-08-31 -
# See PARALLEL_INTEGRATION.md §2. `cost.py` is the only consumer.
PRICE_TABLE_USD: Final[dict[str, float]] = {
    "search.turbo": 0.001,
    "search.fast": 0.001,
    "search.basic": 0.005,
    "search.advanced": 0.005,
    "search.extra_result": 0.001,  # per result beyond the first 10
    "extract.per_url": 0.001,
    "task.lite": 0.005,
    "task.lite-fast": 0.005,
    "task.base": 0.010,
    "task.base-fast": 0.010,
    "task.core": 0.025,
    "task.core-fast": 0.025,
    "task.core2x": 0.050,
    "task.core2x-fast": 0.050,
    "task.pro": 0.100,
    "task.pro-fast": 0.100,
    "responses.low": 0.010,
    "responses.medium": 0.050,
    "responses.high": 0.250,
    "monitor.lite": 0.003,
    "monitor.base": 0.010,
    "entity_search": 0.005,
}
