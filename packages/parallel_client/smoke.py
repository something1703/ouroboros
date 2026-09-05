"""Client-core smoke test (PHASE_04.md §4.1 acceptance): one turbo search, cost
recorded to `cost_events`. Run with `uv run python -m packages.parallel_client.smoke
[project_id]` — needs `.env` populated and a real Postgres reachable (`make test-live`'s
environment), since this writes a real `cost_events` row.
"""

from __future__ import annotations

import sys

from packages.ledger.db import session_scope
from packages.ledger.repositories import ProjectRepo
from packages.parallel_client.cost import CostMeter
from packages.parallel_client.search import search


def main() -> int:
    project_id = sys.argv[1] if len(sys.argv) > 1 else "demo"

    with (
        session_scope() as session,
        CostMeter(session, project_id, api="search", sku="search.turbo"),
    ):
        result = search(
            "Who founded Parallel Web Systems?",
            ["Parallel Web Systems founder"],
            mode="turbo",
            max_results=2,
        )

    print(f"search_id={result.search_id} hits={len(result.hits)}")
    for hit in result.hits:
        print(f"  {hit.title!r} — {hit.url}")

    with session_scope() as session:
        spend = ProjectRepo.spend(session, project_id)
    print(f"project {project_id!r} total spend: ${spend:.4f} (cost_events row written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
