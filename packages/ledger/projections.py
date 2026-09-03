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

from packages.claims.models import Claim, Evidence, Risk

EventKind = Literal["monitor_event", "reverified", "risk_changed"]


def get_client() -> firestore.Client:
    database = os.environ.get("FIRESTORE_DATABASE", "(default)")
    return firestore.Client(database=database)


def _evidence_summary(evidence: Evidence) -> dict[str, object]:
    """A short summary for the claim card: verdict/holder-ish top field, confidence,
    and up to 3 citation URLs — not the full evidence.output blob."""
    top_citations: list[str] = []
    for field_basis in evidence.basis[:3]:
        for citation in field_basis.citations[:1]:
            top_citations.append(citation.url)
    return {
        "method": evidence.method,
        "confidence": evidence.overall_confidence.value,
        "cycle": evidence.cycle,
        "top_citations": top_citations,
    }


class Projector:
    def __init__(self, client: firestore.Client | None = None) -> None:
        self._client = client or get_client()

    def claim_view(
        self,
        claim: Claim,
        *,
        risk: Risk | None,
        evidence: Evidence | None,
        history_count: int,
        monitor_status: str | None,
    ) -> None:
        doc_ref = (
            self._client.collection("projects")
            .document(claim.project_id)
            .collection("claims")
            .document(claim.claim_id)
        )
        data: dict[str, object] = {
            "claim_id": claim.claim_id,
            "category": claim.category.value,
            "entity_text": claim.entity_text,
            "claim_text": claim.claim_text,
            "priority": claim.priority,
            "status": claim.status.value,
            "risk_level": risk.level.value if risk else None,
            "risk_score": risk.score if risk else None,
            "evidence_summary": _evidence_summary(evidence) if evidence else None,
            "monitor_status": monitor_status,
            "history_count": history_count,
            "updated_at": claim.updated_at,
        }
        doc_ref.set(data, merge=True)

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
