"""PHASE_08.md §8.5: generate_eo_pack against the real local Postgres (tests/conftest.py),
same repository layer the endpoint itself uses -- only Firestore (Projector) is stubbed,
since there's no local Firestore in the offline test env.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from packages.claims.enums import ClaimCategory, ClaimKind, Confidence, RiskLevel
from packages.claims.models import (
    Citation,
    Claim,
    Evidence,
    FieldBasis,
    Project,
    Risk,
    SourceRef,
    VerificationEvent,
)
from packages.exports.eo_pdf import generate_eo_pack
from packages.ledger.projections import Projector
from packages.ledger.repositories import ClaimRepo, EvidenceRepo, HistoryRepo, ProjectRepo, RiskRepo

pytestmark = pytest.mark.usefixtures("engine")


def _seed_high_risk_claim(db_session: Session) -> Claim:
    ProjectRepo.upsert(
        db_session,
        Project(
            project_id="demo", studio_id="studio-1", title="Demo Film", created_at=datetime.now(UTC)
        ),
    )
    source = SourceRef(asset_id="asset-1", page=12, excerpt="A Coca-Cola can is on the table.")
    claim = Claim.new(
        project_id="demo",
        studio_id="studio-1",
        kind=ClaimKind.LEGAL,
        category=ClaimCategory.BRAND,
        entity_text="Coca-Cola",
        claim_text="A Coca-Cola can is visible on the table in Sc. 12",
        language="en",
        source=source,
        jurisdictions=["us"],
    )
    ClaimRepo.upsert(db_session, claim)

    evidence = Evidence(
        claim_id=claim.claim_id,
        cycle=1,
        method="search",
        output={"brand_owner": "The Coca-Cola Company", "known_litigiousness": "high"},
        basis=[
            FieldBasis(
                field="brand_owner",
                citations=[
                    Citation(
                        url="https://coca-colacompany.com/trademarks",
                        retrieved_at=datetime.now(UTC),
                    )
                ],
                reasoning="Official trademark page",
                confidence=Confidence.HIGH,
            )
        ],
        overall_confidence=Confidence.HIGH,
        created_at=datetime.now(UTC),
    )
    EvidenceRepo.insert(db_session, evidence)

    RiskRepo.upsert(
        db_session,
        Risk(
            claim_id=claim.claim_id,
            evidence_id=evidence.evidence_id,
            level=RiskLevel.BLOCKING,
            score=0.95,
            rationale="Highly litigious brand, unauthorized use",
            cost_band="unknown",
            assessed_at=datetime.now(UTC),
        ),
    )

    HistoryRepo.append(
        db_session,
        VerificationEvent(
            claim_id=claim.claim_id,
            at=datetime.now(UTC),
            actor="human",
            from_status=None,
            to_status="verified",
            note="Reviewed and confirmed by legal.",
            ref={"user": "legal@studio.example"},
        ),
    )
    db_session.commit()
    return claim


def test_generate_eo_pack_produces_a_real_pdf(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Projector, "get_project_summary", lambda self, _project_id: None)
    _seed_high_risk_claim(db_session)

    pdf_bytes = generate_eo_pack(db_session, "demo")

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_generate_eo_pack_with_no_high_risk_claims(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Projector, "get_project_summary", lambda self, _project_id: None)
    ProjectRepo.upsert(
        db_session,
        Project(
            project_id="demo", studio_id="studio-1", title="Demo Film", created_at=datetime.now(UTC)
        ),
    )
    db_session.commit()

    pdf_bytes = generate_eo_pack(db_session, "demo")

    assert pdf_bytes.startswith(b"%PDF")
