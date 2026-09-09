"""Clearance-log CSV export (PHASE_08.md §8.5): one row per legal claim.

Originally a live Google Sheet via the Sheets/Drive APIs using `sa-dashboard-api`'s
own ambient credentials -- found live (docs/DECISIONS.md): every real attempt failed
with `403 The caller does not have permission` creating the spreadsheet. Root cause
isn't a missing IAM role (both APIs are enabled; no `roles/sheets.*`/`roles/drive.*`
grant exists because Sheets/Drive authorize file *creation* through Drive storage
ownership, not IAM role bindings) -- a bare GCP service account with no Google
Workspace license has zero personal Drive storage quota, so it can never own a newly
created Sheet, regardless of scopes or roles. Fixing that for real needs either a
Workspace domain for delegation or a pre-existing Shared Drive for the service
account to create into, and this project has neither (no GCP Organization exists,
the same constraint that already ruled out Cloud IAP). A CSV to Cloud Storage needs
none of that, reuses this project's own already-working export pattern (eo_pdf.py,
factcheck_pdf.py), and is a completely honest substitute for what a "clearance log"
actually needs to be: one row per legal claim, openable in Sheets/Excel by anyone
with the signed URL.
"""

from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from packages.claims.enums import ClaimKind
from packages.claims.models import Claim, Evidence, Risk
from packages.ledger.repositories import ClaimRepo, EvidenceRepo, RiskRepo

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


def generate_clearance_csv(session: Session, project_id: str) -> bytes:
    """One row per legal (CLEAR) claim. Regenerated fresh on every call -- unlike the
    Sheet this replaced, a CSV has no "same file, updated in place" concept to be
    idempotent about; it's just re-uploaded, exactly like the PDF exports already are.
    """
    claims = [
        claim
        for claim in ClaimRepo.list_by_project(session, project_id, limit=100_000)
        if claim.kind == ClaimKind.LEGAL
    ]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_HEADER)
    for claim in claims:
        evidence = EvidenceRepo.latest_for_claim(session, claim.claim_id)
        risk = RiskRepo.get(session, claim.claim_id)
        writer.writerow(_row_for_claim(claim, evidence, risk))

    return buffer.getvalue().encode("utf-8-sig")  # BOM: Excel needs it to read UTF-8 CSVs correctly
