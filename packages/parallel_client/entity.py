"""Entity Search wrapper — `client.beta.findall.entity_search`, not a standalone
`entity` resource in the real SDK (docs/vendor/parallel/README.md). Used to resolve
publishers/labels/estates when a Task output leaves a `*_rights_holder` field null
(PARALLEL_INTEGRATION.md §4.4).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from packages.parallel_client.client import call, get_client

EntityType = Literal["people", "companies"]

# Found live: the API rejects match_limit < 5 with a 422 (Parallel's own documented
# 5-1000 range, docs/vendor/parallel/README.md).
_MIN_MATCH_LIMIT = 5


class EntityHit(BaseModel):
    name: str
    url: str
    description: str


def search(
    objective: str, entity_type: EntityType, *, limit: int = 25, claim_id: str | None = None
) -> list[EntityHit]:
    match_limit = max(limit, _MIN_MATCH_LIMIT)

    def _call() -> object:
        return get_client().beta.findall.entity_search(
            entity_type=entity_type, objective=objective, match_limit=match_limit
        )

    response = call(_call, api="entity_search", sku="entity_search", claim_id=claim_id)
    return [
        EntityHit(name=e.name, url=e.url, description=e.description)
        for e in response.entities  # type: ignore[attr-defined]
    ]
