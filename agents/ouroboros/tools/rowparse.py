"""Shared parsing of `ledger.get_claim`'s flat JSON row into domain `Claim`/`Evidence`
objects — used by both risk_tools.py and reporter_tools.py."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from packages.claims.enums import ClaimCategory, ClaimKind, Confidence, VerificationStatus
from packages.claims.models import Claim, Evidence, EvidenceMethod, FieldBasis, SourceRef


def claim_from_row(row: dict[str, object]) -> Claim:
    return Claim(
        claim_id=str(row["claim_id"]),
        project_id=str(row["project_id"]),
        studio_id=str(row["studio_id"]),
        kind=ClaimKind(str(row["kind"])),
        category=ClaimCategory(str(row["category"])),
        entity_text=str(row["entity_text"]),
        normalized_text=str(row["normalized_text"]),
        claim_text=str(row["claim_text"]),
        language=str(row["language"]),
        source=SourceRef.model_validate(row["source"]),
        jurisdictions=cast("list[str]", row["jurisdictions"]),
        priority=int(cast(str, row["priority"])),
        status=VerificationStatus(str(row["status"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


def evidence_from_row(row: dict[str, object], *, claim_id: str) -> Evidence | None:
    """None if this claim has no evidence yet (a `get_claim` row's evidence_id is null
    when the LEFT JOIN LATERAL found nothing)."""
    if row.get("evidence_id") is None:
        return None
    basis_raw = cast("list[object]", row.get("evidence_basis") or [])
    method = cast(EvidenceMethod, row["method"])
    return Evidence(
        evidence_id=str(row["evidence_id"]),
        claim_id=claim_id,
        cycle=int(cast(str, row["cycle"])),
        method=method,
        parallel_run_id=cast("str | None", row.get("parallel_run_id")),
        output=cast("dict[str, object]", row.get("evidence_output") or {}),
        basis=[FieldBasis.model_validate(b) for b in basis_raw],
        overall_confidence=Confidence(str(row["overall_confidence"])),
        created_at=datetime.fromisoformat(str(row["evidence_created_at"])),
    )
