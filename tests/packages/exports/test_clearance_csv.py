"""PHASE_08.md §8.5: generate_clearance_csv's row-building, against the real local
Postgres. Replaces test_clearance_sheet.py's Sheets/Drive/Firestore mocking --
docs/DECISIONS.md: sa-dashboard-api has no Google Workspace license and can never
own a newly created Sheet, so the export is a CSV now, with no external API to mock.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from packages.claims.enums import ClaimCategory, ClaimKind, Confidence, RiskLevel
from packages.claims.models import Claim, Evidence, Project, Risk, SourceRef
from packages.exports.clearance_csv import _HEADER, generate_clearance_csv
from packages.ledger.repositories import ClaimRepo, EvidenceRepo, ProjectRepo, RiskRepo


def _seed_legal_claim(db_session: Session) -> Claim:
    ProjectRepo.upsert(
        db_session,
        Project(
            project_id="demo", studio_id="studio-1", title="Demo Film", created_at=datetime.now(UTC)
        ),
    )
    source = SourceRef(
        asset_id="asset-1", page=12, scene_heading="INT. KITCHEN", excerpt="A Coca-Cola can."
    )
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
        output={
            "brand_owner": "The Coca-Cola Company",
            "product_placement_contact_url": "https://coca-colacompany.com/forms/product",
        },
        basis=[],
        overall_confidence=Confidence.HIGH,
        created_at=datetime.now(UTC),
    )
    EvidenceRepo.insert(db_session, evidence)
    RiskRepo.upsert(
        db_session,
        Risk(
            claim_id=claim.claim_id,
            evidence_id=evidence.evidence_id,
            level=RiskLevel.LOW,
            score=0.2,
            rationale="Incidental background use",
            cost_band="none",
            assessed_at=datetime.now(UTC),
        ),
    )
    db_session.commit()
    return claim


def _rows(csv_bytes: bytes) -> list[list[str]]:
    # utf-8-sig strips the BOM the export writes for Excel's benefit -- a plain
    # utf-8 decode would otherwise leave it stuck on the first header cell.
    text = csv_bytes.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def test_generate_clearance_csv_header_and_row(db_session: Session) -> None:
    _seed_legal_claim(db_session)

    csv_bytes = generate_clearance_csv(db_session, "demo")
    rows = _rows(csv_bytes)

    assert rows[0] == _HEADER
    assert len(rows) == 2  # header + the one legal claim
    assert rows[1][2] == "Coca-Cola"  # Item column
    assert rows[1][4] == "The Coca-Cola Company"  # Rights Holder column
    assert rows[1][7] == "low"  # Risk column


def test_generate_clearance_csv_excludes_factual_claims(db_session: Session) -> None:
    _seed_legal_claim(db_session)
    factual = Claim.new(
        project_id="demo",
        studio_id="studio-1",
        kind=ClaimKind.FACTUAL,
        category=ClaimCategory.EVENT,
        entity_text="The 1998 championship game",
        claim_text="The home team won 3-1.",
        language="en",
        source=SourceRef(asset_id="asset-1", page=20, excerpt="..."),
        jurisdictions=["us"],
    )
    ClaimRepo.upsert(db_session, factual)
    db_session.commit()

    rows = _rows(generate_clearance_csv(db_session, "demo"))

    # Only the one legal claim seeded in _seed_legal_claim -- a clearance log is a
    # legal-exposure document, not a factual fact-check (that's factcheck_pdf.py's).
    assert len(rows) == 2
    assert rows[1][2] == "Coca-Cola"


def test_generate_clearance_csv_regenerates_fresh_each_call(db_session: Session) -> None:
    # No "same file, updated in place" idempotency to test here -- unlike the Sheet
    # this replaced, a CSV is just re-uploaded every time. Two calls should each
    # independently reflect the current claim set, not silently reuse stale bytes.
    _seed_legal_claim(db_session)
    first = generate_clearance_csv(db_session, "demo")
    second = generate_clearance_csv(db_session, "demo")
    assert first == second
