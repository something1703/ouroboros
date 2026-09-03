from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.claims.enums import ClaimCategory, ClaimKind, Confidence, VerificationStatus
from packages.claims.models import Claim, Evidence, Project, SourceRef, VerificationEvent
from packages.ledger.repositories import (
    ClaimRepo,
    EvidenceRepo,
    ProjectRepo,
    record_evidence_and_status,
)

pytestmark = pytest.mark.usefixtures("engine")

_NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _project(project_id: str = "demo") -> Project:
    return Project(project_id=project_id, studio_id="studio-1", title="Demo Film", created_at=_NOW)


def _claim(project_id: str = "demo") -> Claim:
    source = SourceRef(asset_id="asset-1", page=12, excerpt="A Coca-Cola can is on the table.")
    return Claim.new(
        project_id=project_id,
        studio_id="studio-1",
        kind=ClaimKind.LEGAL,
        category=ClaimCategory.BRAND,
        entity_text="Coca-Cola",
        claim_text="A Coca-Cola can is visible on the table in Sc. 12",
        language="en",
        source=source,
        jurisdictions=["us"],
    )


def test_project_upsert_is_idempotent(db_session: Session) -> None:
    project = _project()
    ProjectRepo.upsert(db_session, project)
    ProjectRepo.upsert(db_session, project)
    db_session.commit()

    count = db_session.execute(
        text("SELECT COUNT(*) FROM projects WHERE project_id = :id"), {"id": project.project_id}
    ).scalar_one()
    assert count == 1


def test_project_upsert_updates_fields(db_session: Session) -> None:
    project = _project()
    ProjectRepo.upsert(db_session, project)
    db_session.commit()

    updated = project.model_copy(update={"title": "New Title"})
    ProjectRepo.upsert(db_session, updated)
    db_session.commit()

    fetched = ProjectRepo.require(db_session, project.project_id)
    assert fetched.title == "New Title"


def test_claim_upsert_is_idempotent_and_stable_id(db_session: Session) -> None:
    project = _project()
    ProjectRepo.upsert(db_session, project)
    db_session.commit()

    claim = _claim()
    ClaimRepo.upsert(db_session, claim)
    ClaimRepo.upsert(db_session, claim)  # simulates re-ingesting the same script
    db_session.commit()

    count = db_session.execute(
        text("SELECT COUNT(*) FROM claims WHERE claim_id = :id"), {"id": claim.claim_id}
    ).scalar_one()
    assert count == 1


def test_record_evidence_and_status_is_atomic(db_session: Session) -> None:
    project = _project()
    ProjectRepo.upsert(db_session, project)
    claim = _claim()
    ClaimRepo.upsert(db_session, claim)
    db_session.commit()

    evidence = Evidence(
        claim_id=claim.claim_id,
        cycle=1,
        method="task",
        output={"brand_owner": "The Coca-Cola Company"},
        basis=[],
        overall_confidence=Confidence.HIGH,
        created_at=_NOW,
    )
    event = VerificationEvent(
        claim_id=claim.claim_id,
        at=_NOW,
        actor="agent",
        from_status=VerificationStatus.TRIAGED,
        to_status=VerificationStatus.VERIFIED,
        note="verified",
    )
    record_evidence_and_status(
        db_session, evidence=evidence, event=event, new_status=VerificationStatus.VERIFIED
    )
    db_session.commit()

    stored_claim = ClaimRepo.require(db_session, claim.claim_id)
    assert stored_claim.status == VerificationStatus.VERIFIED
    latest = EvidenceRepo.latest_for_claim(db_session, claim.claim_id)
    assert latest is not None
    assert latest.output["brand_owner"] == "The Coca-Cola Company"


def test_record_evidence_and_status_rolls_back_on_failure(db_session: Session) -> None:
    """A failure mid-transaction must not leave a partial evidence/history/status write."""
    project = _project()
    ProjectRepo.upsert(db_session, project)
    claim = _claim()
    ClaimRepo.upsert(db_session, claim)
    db_session.commit()

    evidence = Evidence(
        claim_id=claim.claim_id,
        cycle=1,
        method="task",
        output={},
        basis=[],
        overall_confidence=Confidence.HIGH,
        created_at=_NOW,
    )
    # A history event pointing at a claim_id that doesn't exist violates the
    # verification_history -> claims foreign key. That's a DB-level failure
    # (IntegrityError at flush time), not a Python-level check — unlike the
    # evidence insert just before it in record_evidence_and_status, which
    # SQLAlchemy has already queued for the same not-yet-committed transaction.
    bad_event = VerificationEvent(
        claim_id="does-not-exist",
        at=_NOW,
        actor="agent",
        from_status=VerificationStatus.TRIAGED,
        to_status=VerificationStatus.VERIFIED,
        note="verified",
    )

    with pytest.raises(IntegrityError):
        record_evidence_and_status(
            db_session, evidence=evidence, event=bad_event, new_status=VerificationStatus.VERIFIED
        )
        db_session.flush()
    db_session.rollback()

    # The evidence insert was queued in the same transaction as the failing
    # history append — proving the whole write was discarded, not just the
    # one statement that violated the constraint.
    count = db_session.execute(
        text("SELECT COUNT(*) FROM evidence WHERE claim_id = :id"), {"id": claim.claim_id}
    ).scalar_one()
    assert count == 0


def test_claims_project_status_index_exists_and_is_usable(db_session: Session) -> None:
    """A tiny table's planner picks a seq scan regardless of indexes, so this forces the
    planner's hand (SET enable_seqscan=off) to prove the index is real and queryable,
    rather than just asserting an index *exists* in the catalog."""
    project = _project()
    ProjectRepo.upsert(db_session, project)
    ClaimRepo.upsert(db_session, _claim())
    db_session.commit()

    db_session.execute(text("SET LOCAL enable_seqscan = off"))
    plan = db_session.execute(
        text("EXPLAIN SELECT * FROM claims WHERE project_id = :p AND status = :s"),
        {"p": project.project_id, "s": "pending"},
    ).all()
    plan_text = "\n".join(row[0] for row in plan)
    assert "ix_claims_project_status" in plan_text
