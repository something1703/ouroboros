"""Firestore projections — denormalized live views for the dashboard. Firestore is a
derived projection of Cloud SQL (the source of truth, packages/ledger/repositories.py);
every write here follows a successful ledger commit. See DATA_MODEL.md §4 and
ARCHITECTURE.md §2.2.

Single-writer rule: only `services/*` call `Projector` methods, after their own
Cloud SQL transaction commits. Nothing else writes to these Firestore documents.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from google.cloud import firestore

EventKind = Literal["monitor_event", "reverified", "risk_changed"]


def get_client() -> firestore.Client:
    database = os.environ.get("FIRESTORE_DATABASE", "(default)")
    # `project=` passed explicitly rather than left to firestore.Client's own implicit
    # auto-detection (docs/DECISIONS.md #070) -- found live, reproducible on 2/2 CLEAR
    # pass attempts: the agent's very first Firestore write (RiskAssessor's
    # write_claim_view, on a module-level Projector() built at import time during a
    # fresh Agent Engine cold start) failed with `404 The database (default) does not
    # exist`, for a project/database that a plain script confirmed real seconds later.
    # GOOGLE_CLOUD_PROJECT is a *reserved* env var name on Agent Engine deployments
    # (Vertex AI rejects setting it explicitly) -- reserved because the platform
    # injects it itself, so reading it here is reliable even though `agents/deploy/
    # deploy.py` never sets it. Passing it straight to the constructor sidesteps
    # whatever the SDK's own default-project detection was racing against.
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    return firestore.Client(project=project, database=database)


class Projector:
    def __init__(self, client: firestore.Client | None = None) -> None:
        self._client = client or get_client()

    def claim_view(
        self,
        *,
        project_id: str,
        claim_id: str,
        category: str,
        entity_text: str,
        claim_text: str,
        priority: int,
        status: str,
        updated_at: datetime,
        risk_level: str | None,
        risk_score: float | None,
        evidence_summary: dict[str, object] | None,
        history_count: int,
        monitor_status: str | None,
    ) -> None:
        """Takes already-known primitives, not `Claim`/`Risk`/`Evidence` domain objects
        (docs/DECISIONS.md #067) — the only two callers either already have these values
        in hand from their own Cloud SQL transaction (`services/ingest`) or can only
        reach this data via Toolbox, not a live DB session (`agents/ouroboros/tools/
        firestore_tools.py`, which builds `evidence_summary` itself from Toolbox JSON),
        so a shared domain-object signature bought nothing and forced the second caller
        into a DB connection that hangs forever from the Agent Engine's runtime."""
        doc_ref = (
            self._client.collection("projects")
            .document(project_id)
            .collection("claims")
            .document(claim_id)
        )
        data: dict[str, object] = {
            "claim_id": claim_id,
            "category": category,
            "entity_text": entity_text,
            "claim_text": claim_text,
            "priority": priority,
            "status": status,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "evidence_summary": evidence_summary,
            "monitor_status": monitor_status,
            "history_count": history_count,
            "updated_at": updated_at,
        }
        doc_ref.set(data, merge=True)

    def claim_summary(self, project_id: str, claim_id: str, summary_md: str) -> None:
        """Merge-writes just the human-readable summary Reporter generates (ADK_AGENTS.md
        §2.4) onto an existing claim_view document — a separate, small write rather than
        widening `claim_view`'s own signature, since Reporter runs after (and doesn't
        otherwise touch) whatever `claim_view` last wrote for this claim."""
        doc_ref = (
            self._client.collection("projects")
            .document(project_id)
            .collection("claims")
            .document(claim_id)
        )
        doc_ref.set({"summary_md": summary_md}, merge=True)

    def project_summary(
        self,
        project_id: str,
        *,
        title: str,
        release_date: date | None,
        counts_by_status: dict[str, int],
        counts_by_risk: dict[str, int],
        reality_drift: float,
        spend_usd: Decimal,
    ) -> None:
        doc_ref = self._client.collection("projects").document(project_id)
        data: dict[str, object] = {
            "title": title,
            "release_date": release_date.isoformat() if release_date else None,
            "counts_by_status": counts_by_status,
            "counts_by_risk": counts_by_risk,
            "reality_drift": reality_drift,
            "spend_usd": float(spend_usd),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        doc_ref.set(data, merge=True)

    def event_entry(
        self,
        project_id: str,
        *,
        event_id: str,
        at: datetime,
        claim_id: str,
        kind: EventKind,
        summary: str,
        delta: dict[str, object] | None = None,
    ) -> None:
        doc_ref = (
            self._client.collection("projects")
            .document(project_id)
            .collection("events")
            .document(event_id)
        )
        doc_ref.set(
            {
                "at": at,
                "claim_id": claim_id,
                "kind": kind,
                "summary": summary,
                "delta": delta or {},
            }
        )

    def run_progress(
        self,
        project_id: str,
        run_id: str,
        *,
        stage: str,
        done: int,
        total: int,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        doc_ref = (
            self._client.collection("projects")
            .document(project_id)
            .collection("runs")
            .document(run_id)
        )
        data: dict[str, object] = {"stage": stage, "done": done, "total": total}
        if started_at is not None:
            data["started_at"] = started_at
        if finished_at is not None:
            data["finished_at"] = finished_at
        doc_ref.set(data, merge=True)
