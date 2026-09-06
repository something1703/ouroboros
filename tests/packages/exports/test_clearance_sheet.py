"""PHASE_08.md §8.5: export_clearance_sheet's row-building and idempotent create-vs-
update logic, against the real local Postgres -- Sheets/Drive/Firestore are mocked
(no real Google Workspace credentials in the offline test env)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

import packages.exports.clearance_sheet as clearance_sheet
from packages.claims.enums import ClaimCategory, ClaimKind, Confidence, RiskLevel
from packages.claims.models import Claim, Evidence, Project, Risk, SourceRef
from packages.ledger.repositories import ClaimRepo, EvidenceRepo, ProjectRepo, RiskRepo

pytestmark = pytest.mark.usefixtures("engine")


class _FakeDoc:
    def __init__(self, exists: bool, data: dict[str, Any] | None = None) -> None:
        self.exists = exists
        self._data = data or {}

    def to_dict(self) -> dict[str, Any]:
        return self._data

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        self._data.update(data)


class _FakeDocRef:
    def __init__(self, doc: _FakeDoc) -> None:
        self._doc = doc

    def get(self) -> _FakeDoc:
        return self._doc

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        self._doc.set(data, merge=merge)


class _FakeCollection:
    def __init__(self, doc: _FakeDoc) -> None:
        self._doc = doc

    def document(self, _project_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._doc)


class _FakeFirestoreClient:
    def __init__(self, existing_sheet_id: str | None = None) -> None:
        data = {"clearance_sheet_id": existing_sheet_id} if existing_sheet_id else None
        self._doc = _FakeDoc(exists=existing_sheet_id is not None, data=data)

    def collection(self, _name: str) -> _FakeCollection:
        return _FakeCollection(self._doc)


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


def test_export_creates_a_new_sheet_and_shares_it(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_legal_claim(db_session)

    fake_sheets = MagicMock()
    fake_sheets.spreadsheets().create().execute.return_value = {"spreadsheetId": "sheet-123"}
    fake_drive = MagicMock()
    fake_firestore = _FakeFirestoreClient(existing_sheet_id=None)

    monkeypatch.setattr(clearance_sheet, "_sheets_service", lambda: fake_sheets)
    monkeypatch.setattr(clearance_sheet, "_drive_service", lambda: fake_drive)
    monkeypatch.setattr(clearance_sheet, "get_firestore_client", lambda: fake_firestore)

    url = clearance_sheet.export_clearance_sheet(db_session, "demo")

    assert url == "https://docs.google.com/spreadsheets/d/sheet-123"
    fake_drive.permissions().create.assert_called_with(
        fileId="sheet-123", body={"type": "anyone", "role": "reader"}
    )
    update_call = fake_sheets.spreadsheets().values().update
    rows = update_call.call_args.kwargs["body"]["values"]
    assert rows[0] == clearance_sheet._HEADER
    assert rows[1][2] == "Coca-Cola"  # Item column
    assert rows[1][4] == "The Coca-Cola Company"  # Rights Holder column
    assert rows[1][7] == "low"  # Risk column


def test_export_reuses_existing_sheet_and_clears_before_rewriting(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_legal_claim(db_session)

    fake_sheets = MagicMock()
    fake_drive = MagicMock()
    fake_firestore = _FakeFirestoreClient(existing_sheet_id="existing-sheet-456")

    monkeypatch.setattr(clearance_sheet, "_sheets_service", lambda: fake_sheets)
    monkeypatch.setattr(clearance_sheet, "_drive_service", lambda: fake_drive)
    monkeypatch.setattr(clearance_sheet, "get_firestore_client", lambda: fake_firestore)

    url = clearance_sheet.export_clearance_sheet(db_session, "demo")

    assert url == "https://docs.google.com/spreadsheets/d/existing-sheet-456"
    fake_sheets.spreadsheets().create.assert_not_called()
    fake_drive.permissions().create.assert_not_called()
    fake_sheets.spreadsheets().values().clear.assert_called_with(
        spreadsheetId="existing-sheet-456", range="A:Z", body={}
    )
