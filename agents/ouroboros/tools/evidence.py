"""Shared evidence-writing/status-transition helpers, used by every per-claim
verification loop (`clear/specialist.py`, `truecut/fact.py`, `truecut/archive.py`) —
the same "read current cycle, write the next one, append a status transition" sequence
regardless of which head or method produced the evidence.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal

from agents.ouroboros.tools import ledger
from packages.claims.enums import Confidence
from packages.claims.models import FieldBasis
from packages.common.ids import new_ulid


def current_cycle(claim_id: str) -> int:
    raw = ledger.get_claim(claim_id=claim_id)
    row = json.loads(raw) if raw else None
    if not row or row.get("cycle") is None:
        return 0
    return int(row["cycle"])


def write_evidence(
    claim_id: str,
    *,
    method: str,
    content: dict[str, object],
    basis: Sequence[FieldBasis],
    confidence: Confidence,
    cost_usd: Decimal,
    parallel_run_id: str | None = None,
    processor: str | None = None,
) -> None:
    expected_cycle = current_cycle(claim_id) + 1
    ledger.record_evidence(
        evidence_id=new_ulid(),
        claim_id=claim_id,
        expected_cycle=expected_cycle,
        method=method,
        output_json=json.dumps(content),
        basis_json=json.dumps([b.model_dump(mode="json") for b in basis]),
        overall_confidence=confidence.value,
        cost_usd=float(cost_usd),
        parallel_run_id=parallel_run_id or "",
        processor=processor or "",
    )


def set_status(claim_id: str, status: str, *, note: str) -> None:
    ledger.set_status(
        claim_id=claim_id,
        new_status=status,
        actor="agent",
        note=note,
        ref_json="{}",
        event_id=new_ulid(),
    )
