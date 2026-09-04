"""Seeds local-dev-only fixture data for evals/adk/*.evalset.json (PHASE_05.md
§5.2/§5.4): 5 small, isolated projects (eval-triage-1..5) for ClaimTriage cases.
RiskAssessor's eval cases reuse the real "demo" project's already-verified claims
instead (run a real local CLEAR pass on demo first if those need re-populating).

Usage: DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev \
       uv run python scripts/seed_eval_fixtures.py
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from packages.claims.enums import ClaimCategory, ClaimKind
from packages.claims.models import Asset, Claim, Project, SourceRef
from packages.claims.normalize import normalize_text
from packages.ledger.db import session_scope
from packages.ledger.repositories import AssetRepo, ClaimRepo, PriorDecisionRepo, ProjectRepo


def _project(project_id: str) -> Project:
    return Project(
        project_id=project_id,
        studio_id="studio-eval",
        title="Eval Fixture",
        release_date=date(2026, 12, 1),
        shooting_countries=["us"],
        distribution_territories=["us", "gb"],
        budget_cap_usd=Decimal("10.00"),
        created_at=datetime.now(UTC),
    )


def _asset(project_id: str) -> Asset:
    return Asset(
        asset_id=f"{project_id}-asset",
        project_id=project_id,
        kind="script",
        gcs_uri="gs://local-dev/fake.pdf",
        language="en",
        page_count=1,
        ingested_at=datetime.now(UTC),
    )


def _claim(project_id: str, *, category: str, entity: str, text: str, priority: int = 3) -> Claim:
    source = SourceRef(asset_id=f"{project_id}-asset", page=1, excerpt=text)
    return Claim.new(
        project_id=project_id,
        studio_id="studio-eval",
        kind=ClaimKind.LEGAL,
        category=ClaimCategory(category),
        entity_text=entity,
        claim_text=text,
        language="en",
        source=source,
        jurisdictions=["us", "gb"],
        priority=priority,
    )


def main() -> None:
    with session_scope() as session:
        # eval-triage-1: one simple pending music claim, no prior decision.
        ProjectRepo.upsert(session, _project("eval-triage-1"))
        AssetRepo.upsert(session, _asset("eval-triage-1"))
        ClaimRepo.upsert_many(
            session,
            [
                _claim(
                    "eval-triage-1",
                    category="music",
                    entity="Here Comes the Sun",
                    text="A record player spins Here Comes the Sun by The Beatles.",
                    priority=1,
                )
            ],
        )

        # eval-triage-2: one pending brand claim WITH a matching prior decision -> skip.
        ProjectRepo.upsert(session, _project("eval-triage-2"))
        AssetRepo.upsert(session, _asset("eval-triage-2"))
        ClaimRepo.upsert_many(
            session,
            [
                _claim(
                    "eval-triage-2",
                    category="brand",
                    entity="Pepsi",
                    text="A Pepsi vending machine hums in the corner of the diner.",
                    priority=3,
                )
            ],
        )
        PriorDecisionRepo.add(
            session,
            studio_id="studio-eval",
            category="brand",
            entity_normalized=normalize_text("Pepsi"),
            decision="cleared",
            note="Standing studio clearance for background Pepsi signage, decided 2026-01-15.",
            decided_at=datetime(2026, 1, 15, tzinfo=UTC),
        )

        # eval-triage-3: two pending claims, different categories, batched together.
        ProjectRepo.upsert(session, _project("eval-triage-3"))
        AssetRepo.upsert(session, _asset("eval-triage-3"))
        ClaimRepo.upsert_many(
            session,
            [
                _claim(
                    "eval-triage-3",
                    category="location",
                    entity="Eiffel Tower",
                    text="EXT. EIFFEL TOWER - NIGHT",
                    priority=3,
                ),
                _claim(
                    "eval-triage-3",
                    category="person",
                    entity="Serena Williams",
                    text="A poster of Serena Williams hangs in the gym.",
                    priority=1,
                ),
            ],
        )

        # eval-triage-4: one pending artwork claim (shares the location_artwork spec).
        ProjectRepo.upsert(session, _project("eval-triage-4"))
        AssetRepo.upsert(session, _asset("eval-triage-4"))
        ClaimRepo.upsert_many(
            session,
            [
                _claim(
                    "eval-triage-4",
                    category="artwork",
                    entity="Starry Night replica",
                    text="A framed replica of Starry Night hangs above the fireplace.",
                    priority=3,
                )
            ],
        )

        # eval-triage-5: one pending claim with a prior decision for a DIFFERENT entity
        # -> not skipped (tests that the prior-decision lookup is entity-specific, not
        # project-wide).
        ProjectRepo.upsert(session, _project("eval-triage-5"))
        AssetRepo.upsert(session, _asset("eval-triage-5"))
        ClaimRepo.upsert_many(
            session,
            [
                _claim(
                    "eval-triage-5",
                    category="music",
                    entity="Imagine",
                    text="Imagine by John Lennon plays softly in the background.",
                    priority=1,
                )
            ],
        )
        PriorDecisionRepo.add(
            session,
            studio_id="studio-eval",
            category="music",
            entity_normalized=normalize_text("A Completely Different Song"),
            decision="cleared",
            note="Unrelated prior decision -- must not cause eval-triage-5's claim to skip.",
            decided_at=datetime(2026, 1, 15, tzinfo=UTC),
        )

        print("seeded 5 eval-triage fixture projects")


if __name__ == "__main__":
    main()
