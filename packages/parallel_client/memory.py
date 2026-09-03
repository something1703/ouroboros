"""Memory wrapper. See PARALLEL_INTEGRATION.md §4.7. Every result kind (`task`,
`monitor`, `findall`) carries its own `input_excerpt`; only `task` also carries
`output_excerpt` — used as `prior_context` in a Task's input hints (quoted, untrusted).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from packages.common.errors import ParallelValidationError
from packages.common.logging import get_logger
from packages.parallel_client.client import call, get_client

log = get_logger(__name__)

MemoryKind = Literal["task", "monitor", "findall"]

_warned_disabled = False


class MemoryHit(BaseModel):
    id: str
    kind: str
    input_excerpt: str
    output_excerpt: str | None = None


def retrieve(
    query: str, scope_key: str, *, kind: MemoryKind | None = None, limit: int = 10
) -> list[MemoryHit]:
    """Graceful no-op if the org has memory disabled (logged once, not per call)."""
    global _warned_disabled

    def _call() -> object:
        return get_client().beta.memory.retrieve(
            query=query, memory_scope_key=scope_key, kind=kind, limit=limit
        )

    try:
        response = call(_call, api="memory_retrieve", sku="memory.retrieve")
    except ParallelValidationError as exc:
        if not _warned_disabled:
            log.warning("memory_unavailable", scope_key=scope_key, error=str(exc))
            _warned_disabled = True
        return []

    hits: list[MemoryHit] = []
    for result in response.results:  # type: ignore[attr-defined]
        hits.append(
            MemoryHit(
                id=result.id,
                kind=result.kind or "unknown",
                input_excerpt=result.input_excerpt,
                output_excerpt=getattr(result, "output_excerpt", None),
            )
        )
    return hits
