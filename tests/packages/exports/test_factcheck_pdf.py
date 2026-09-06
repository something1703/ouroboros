"""PHASE_08.md §8.5: generate_factcheck_report against the real local Postgres."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from packages.claims.enums import ClaimCategory, ClaimKind, Confidence
from packages.claims.models import Claim, Evidence, Project, SourceRef
from packages.exports.factcheck_pdf import generate_factcheck_report
from packages.ledger.repositories import ClaimRepo, EvidenceRepo, ProjectRepo

pytestmark = pytest.mark.usefixtures("engine")


def _seed_factual_claim(db_session: Session, *, t_start_ms: int) -> Claim:
    source = SourceRef(
        asset_id="cut-1",
        t_start_ms=t_start_ms,
        t_end_ms=t_start_ms + 4000,
        channel="narration",
        excerpt="The broadcast reached over a billion viewers.",
    )
    claim = Claim.new(
        project_id="demo",
        studio_id="studio-1",
        kind=ClaimKind.FACTUAL,
        category=ClaimCategory.STATISTIC,
        entity_text="Apollo 11 broadcast viewership",
        claim_text="The broadcast reached over a billion viewers.",
        language="en",
        source=source,
        jurisdictions=["us"],
    )
    ClaimRepo.upsert(db_session, claim)
    evidence = Evidence(
        claim_id=claim.claim_id,
        cycle=1,
        method="grounding",
        output={
            "verdict": "contradicted",
            "corrected_statement": "The broadcast reached an estimated 600 million viewers.",
            "key_evidence_summary": "Contemporary estimates place the audience in the hundreds of millions.",
            "is_developing_story": False,
            "recommended_wording": None,
        },
        basis=[],
        overall_confidence=Confidence.MEDIUM,
        created_at=datetime.now(UTC),
    )
    EvidenceRepo.insert(db_session, evidence)
    db_session.commit()
    return claim


def test_generate_factcheck_report_produces_a_real_pdf(db_session: Session) -> None:
    ProjectRepo.upsert(
        db_session,
        Project(
            project_id="demo", studio_id="studio-1", title="Demo Film", created_at=datetime.now(UTC)
        ),
    )
    db_session.commit()
    _seed_factual_claim(db_session, t_start_ms=90_000)

    pdf_bytes = generate_factcheck_report(db_session, "demo")

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_generate_factcheck_report_orders_by_timecode(db_session: Session) -> None:
    ProjectRepo.upsert(
        db_session,
        Project(
            project_id="demo", studio_id="studio-1", title="Demo Film", created_at=datetime.now(UTC)
        ),
    )
    db_session.commit()
    later = _seed_factual_claim(db_session, t_start_ms=120_000)
    earlier = _seed_factual_claim(db_session, t_start_ms=30_000)

    claims = [
        c
        for c in ClaimRepo.list_by_project(db_session, "demo", limit=100_000)
        if c.kind == ClaimKind.FACTUAL
    ]
    from packages.exports.factcheck_pdf import _sort_key

    claims.sort(key=_sort_key)
    assert [c.claim_id for c in claims] == [earlier.claim_id, later.claim_id]
