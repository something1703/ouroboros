"""Firestore projection tools — thin wrappers around packages/ledger/projections.py,
used by RiskAssessor and Reporter (ADK_AGENTS.md §2.3, §2.4).

`write_claim_view`/`write_project_summary` source their Cloud-SQL-backed data via
Toolbox (`agents.ouroboros.tools.ledger`), not a direct DB session — found live
(docs/DECISIONS.md #067): the deployed Agent Engine's runtime has no VPC path to Cloud
SQL's private IP (the same root cause as #062), so a direct SQLAlchemy connection here
hangs until timeout and crashes the whole run. The actual Firestore *write* still
happens in-process via `Projector` — Firestore is reachable over the public internet,
unlike Cloud SQL's private IP.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from packages.ledger.projections import Projector

from . import ledger
from .resilience import resilient

_projector = Projector()


def _claim_evidence_summary(claim: dict[str, object]) -> dict[str, object] | None:
    """Mirrors packages/ledger/projections.py's old `_evidence_summary`, but built from
    `get_claim`'s flat Toolbox JSON (evidence_id/method/overall_confidence/cycle/
    evidence_basis) instead of a typed `Evidence` object."""
    if not claim.get("evidence_id"):
        return None
    basis: list[dict[str, object]] = claim.get("evidence_basis") or []  # type: ignore[assignment]
    top_citations: list[str] = []
    for field_basis in basis[:3]:
        citations: list[dict[str, object]] = field_basis.get("citations") or []  # type: ignore[assignment]
        if citations:
            top_citations.append(str(citations[0]["url"]))
    return {
        "method": claim["method"],
        "confidence": claim["overall_confidence"],
        "cycle": claim["cycle"],
        "top_citations": top_citations,
    }


@resilient
def write_claim_view(claim_id: str) -> dict[str, object]:
    """Refresh the Firestore live-view document for one claim from its current Cloud
    SQL state (claim, risk, latest evidence, history count)."""
    claim = json.loads(ledger.get_claim(claim_id=claim_id))
    history_count = json.loads(ledger.count_history(claim_id=claim_id))["count"]
    _projector.claim_view(
        project_id=claim["project_id"],
        claim_id=claim["claim_id"],
        category=claim["category"],
        entity_text=claim["entity_text"],
        claim_text=claim["claim_text"],
        priority=claim["priority"],
        status=claim["status"],
        updated_at=datetime.fromisoformat(claim["updated_at"]),
        risk_level=claim.get("risk_level"),
        risk_score=claim.get("risk_score"),
        evidence_summary=_claim_evidence_summary(claim),
        history_count=history_count,
        monitor_status=None,
    )
    return {"claim_id": claim_id, "written": True}


@resilient
def write_claim_summary(project_id: str, claim_id: str, summary_md: str) -> dict[str, object]:
    """Write Reporter's ≤60-word human-readable summary (with [n] citation indices)
    for one claim into its Firestore live-view document."""
    _projector.claim_summary(project_id, claim_id, summary_md)
    return {"claim_id": claim_id, "written": True}


def _as_rows(raw: str) -> list[dict[str, object]]:
    """Toolbox's postgres-sql tools return a bare object for exactly one row, a JSON
    array for N>1, and (found live testing this) apparently nothing meaningful to parse
    for zero rows here either -- normalize all three to a list."""
    parsed = json.loads(raw) if raw else None
    if parsed is None:
        return []
    return parsed if isinstance(parsed, list) else [parsed]


@resilient
def write_project_summary(project_id: str) -> dict[str, object]:
    """Refresh the Firestore project-summary document: counts by status/risk, spend."""
    project = json.loads(ledger.get_project(project_id=project_id))
    counts_by_status: dict[str, int] = {
        str(row["status"]): int(row["count"])  # type: ignore[call-overload]
        for row in _as_rows(ledger.project_status_counts(project_id=project_id))
    }
    counts_by_risk: dict[str, int] = {
        str(row["level"]): int(row["count"])  # type: ignore[call-overload]
        for row in _as_rows(ledger.project_risk_counts(project_id=project_id))
    }
    spend_usd = json.loads(ledger.check_budget(project_id=project_id))["spend_usd"]
    release_date = project.get("release_date")
    _projector.project_summary(
        project_id,
        title=project["title"],
        # Toolbox serializes the `date` column as a full timestamp (e.g.
        # "2026-10-10T00:00:00Z"), not a bare "YYYY-MM-DD" -- found live testing this.
        release_date=(
            datetime.fromisoformat(release_date.replace("Z", "+00:00")).date()
            if release_date
            else None
        ),
        counts_by_status=counts_by_status,
        counts_by_risk=counts_by_risk,
        reality_drift=0.0,
        spend_usd=Decimal(str(spend_usd)),
    )
    return {"project_id": project_id, "written": True, "spend_usd": float(spend_usd)}


@resilient
def write_run_progress(
    run_id: str, project_id: str, *, stage: str, done: int, total: int
) -> dict[str, object]:
    """Update the Firestore run-progress document the dashboard streams during a CLEAR
    or TRUE CUT run."""
    _projector.run_progress(project_id, run_id, stage=stage, done=done, total=total)
    return {"run_id": run_id, "stage": stage, "done": done, "total": total}
