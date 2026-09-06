"""Clearance-log Google Sheets export (PHASE_08.md §8.5): one row per legal claim,
via the Sheets API using `sa-dashboard-api`'s own ambient credentials (same
`google.auth.default()` pattern `main.py::_generate_signed_url` already uses -- Cloud
Run's attached service account already carries the broad `cloud-platform` scope, so no
explicit scope list is needed here either).

Idempotent per project: the created spreadsheet's ID is stored in Firestore
(`exports/{project_id}`) so re-running the export updates the same sheet instead of
spawning a new one each time -- this codebase's own idempotent-job convention
(`scripts/ingest_private_corpus.py`, `tighten_monitors`), not a special case here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache
from typing import Any

import google.auth
from googleapiclient.discovery import Resource, build
from sqlalchemy.orm import Session

from packages.claims.enums import ClaimKind
from packages.claims.models import Claim, Evidence, Risk
from packages.ledger.projections import get_client as get_firestore_client
from packages.ledger.repositories import ClaimRepo, EvidenceRepo, ProjectRepo, RiskRepo

_HEADER = [
    "Scene",
    "Page",
    "Item",
    "Category",
    "Rights Holder",
    "Contact",
    "Status",
    "Risk",
    "Cost Band",
    "Notes",
    "Last Verified",
]

# Per-category evidence output field names carrying a rights-holder / contact value
# (DATA_MODEL.md §2's Parallel Task output schemas) -- tried in order, first non-empty
# value wins, since e.g. a music claim may only have populated one of the two rights
# fields depending on whether a specific recording (vs. just the composition) applies.
_RIGHTS_HOLDER_FIELDS: dict[str, tuple[str, ...]] = {
    "music": ("composition_rights_holder", "master_rights_holder"),
    "brand": ("brand_owner",),
    "person": ("estate_or_representation",),
    "location": ("owner_or_custodian", "artwork_rights_holder"),
    "artwork": ("artwork_rights_holder", "owner_or_custodian"),
}
_CONTACT_FIELDS: dict[str, tuple[str, ...]] = {
    "music": ("licensing_contact_url",),
    "brand": ("product_placement_contact_url",),
    "location": ("permit_authority_url",),
    "artwork": ("permit_authority_url",),
}


def _first_present(output: dict[str, object], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = output.get(field)
        if value:
            return str(value)
    return ""


def _row_for_claim(claim: Claim, evidence: Evidence | None, risk: Risk | None) -> list[str]:
    output = evidence.output if evidence else {}
    category = claim.category.value
    return [
        claim.source.scene_heading or claim.source.scene_number or "",
        str(claim.source.page) if claim.source.page is not None else "",
        claim.entity_text,
        category,
        _first_present(output, _RIGHTS_HOLDER_FIELDS.get(category, ())),
        _first_present(output, _CONTACT_FIELDS.get(category, ())),
        claim.status.value,
        risk.level.value if risk else "unassessed",
        (risk.cost_band or "") if risk else "",
        risk.rationale if risk else "",
        evidence.created_at.strftime("%Y-%m-%d") if evidence else "",
    ]


@cache
def _sheets_service() -> Resource:
    credentials, _ = google.auth.default()
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


@cache
def _drive_service() -> Resource:
    credentials, _ = google.auth.default()
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _get_existing_spreadsheet_id(firestore_client: Any, project_id: str) -> str | None:
    doc = firestore_client.collection("exports").document(project_id).get()
    if not doc.exists:
        return None
    sheet_id = (doc.to_dict() or {}).get("clearance_sheet_id")
    return str(sheet_id) if sheet_id else None


def _save_spreadsheet_id(firestore_client: Any, project_id: str, spreadsheet_id: str) -> None:
    firestore_client.collection("exports").document(project_id).set(
        {"clearance_sheet_id": spreadsheet_id, "updated_at": datetime.now(UTC)}, merge=True
    )


def export_clearance_sheet(session: Session, project_id: str) -> str:
    """Creates (first call) or updates (subsequent calls) the project's clearance-log
    Google Sheet and returns its URL. One row per legal (CLEAR) claim."""
    project = ProjectRepo.require(session, project_id)
    claims = [
        claim
        for claim in ClaimRepo.list_by_project(session, project_id, limit=100_000)
        if claim.kind == ClaimKind.LEGAL
    ]

    rows: list[list[str]] = [_HEADER]
    for claim in claims:
        evidence = EvidenceRepo.latest_for_claim(session, claim.claim_id)
        risk = RiskRepo.get(session, claim.claim_id)
        rows.append(_row_for_claim(claim, evidence, risk))

    firestore_client = get_firestore_client()
    spreadsheet_id = _get_existing_spreadsheet_id(firestore_client, project_id)
    sheets = _sheets_service()

    if spreadsheet_id is None:
        spreadsheet = (
            sheets.spreadsheets()
            .create(body={"properties": {"title": f"{project.title} — Clearance Log"}})
            .execute()
        )
        spreadsheet_id = spreadsheet["spreadsheetId"]
        _save_spreadsheet_id(firestore_client, project_id, spreadsheet_id)
        # Demo-scoped, synthetic fixture data (docs/evidence): link-accessible read-only
        # so the export is actually openable from the dashboard without per-user sharing.
        _drive_service().permissions().create(
            fileId=spreadsheet_id, body={"type": "anyone", "role": "reader"}
        ).execute()
    else:
        # A shrinking claim list (removed/re-categorized) must not leave stale rows --
        # clear the whole sheet before rewriting rather than only overwriting in place.
        sheets.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id, range="A:Z", body={}
        ).execute()

    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
