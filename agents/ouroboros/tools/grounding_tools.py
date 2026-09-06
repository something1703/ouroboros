"""ADK-compatible wrapper around packages/gemini_client/grounding.py (PHASE_08.md
§8.4). Named separately from parallel_tools.py because this calls Gemini directly
(Parallel is a grounding tool Gemini invokes internally), not Parallel's own API.
"""

from __future__ import annotations

import json

from packages.common.logging import get_logger
from packages.gemini_client.grounding import ask_grounded as _ask_grounded

log = get_logger(__name__)


def ask_grounded(question: str, location: str = "us") -> str:
    """Ask a live, web-grounded question via Gemini + Parallel search (only when the
    claim ledger and private corpus don't already answer it). `location` is an ISO
    country code steering Parallel's search (default "us"). Returns a JSON object
    `{"text", "citations": [{"url","title"}], "web_search_queries"}`."""
    result = _ask_grounded(question, location=location)
    # PHASE_08.md §8.4's acceptance criteria requires this logged, not just returned.
    log.info(
        "ask_grounded_web_search_queries",
        question=question,
        web_search_queries=result["web_search_queries"],
    )
    return json.dumps(result)
