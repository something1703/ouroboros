#!/usr/bin/env python3
"""Seed the demo project and studio memory. Idempotent — safe to run twice.

Usage: uv run python scripts/seed.py [--project fixtures/projects/demo.yaml]
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from packages.claims.models import Project
from packages.ledger.db import session_scope
from packages.ledger.repositories import PriorDecisionRepo, ProjectRepo

# Three synthetic prior clearance decisions for the demo studio — exercises
# ClaimTriage's "skip claims with a recent cleared prior decision" rule
# (ADK_AGENTS.md §2.1) and the studio-memory story in the demo.
_PRIOR_DECISIONS: list[dict[str, str]] = [
    {
        "category": "music",
        "entity_normalized": "happy birthday to you",
        "decision": "cleared",
        "note": "Public domain in the US since the 2016 Warner/Chappell settlement.",
    },
    {
        "category": "brand",
        "entity_normalized": "pepsi",
        "decision": "requires_license",
        "note": "A prior production needed a product-placement agreement for on-screen use.",
    },
    {
        "category": "person",
        "entity_normalized": "a fictional public figure",
        "decision": "cleared",
        "note": "Consent obtained and on file from a prior production.",
    },
]


def seed_project(fixture_path: Path) -> str:
    with fixture_path.open() as f:
        data = yaml.safe_load(f)

    project = Project(
        project_id=data["project_id"],
        studio_id=data["studio_id"],
        title=data["title"],
        release_date=data.get("release_date"),
        shooting_countries=data.get("shooting_countries", []),
        distribution_territories=data.get("distribution_territories", []),
        budget_cap_usd=data.get("budget_cap_usd", 10.00),
        created_at=datetime.now(UTC),
    )

    with session_scope() as session:
        ProjectRepo.upsert(session, project)

        for decision in _PRIOR_DECISIONS:
            existing = PriorDecisionRepo.find(
                session, project.studio_id, decision["entity_normalized"]
            )
            if any(row.decision == decision["decision"] for row in existing):
                continue
            PriorDecisionRepo.add(
                session,
                studio_id=project.studio_id,
                category=decision["category"],
                entity_normalized=decision["entity_normalized"],
                decision=decision["decision"],
                note=decision["note"],
                decided_at=datetime.now(UTC),
            )

    return project.project_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        type=Path,
        default=Path("fixtures/projects/demo.yaml"),
        help="Path to a project metadata YAML file (default: fixtures/projects/demo.yaml)",
    )
    args = parser.parse_args()

    if not args.project.exists():
        print(f"error: {args.project} not found", file=sys.stderr)
        return 1

    project_id = seed_project(args.project)
    print(f"seeded project '{project_id}' from {args.project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
