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
        # Lazy: `get_client()` needs real ADC, which a module-level `Projector()`
        # (agents/ouroboros/tools/firestore_tools.py, services/dashboard_api/runs.py)
        # doesn't have during CI's offline test collection (no google-github-actions/
        # auth step there, deliberately — see packages/common/tracing.py's matching
        # fix). Resolving on first real method call, not at construction, means
        # importing these modules never needs credentials that only exist once deployed.
        self._client_override = client
        self._client_lazy: firestore.Client | None = None

    @property
    def _client(self) -> firestore.Client:
        if self._client_override is not None:
            return self._client_override
        if self._client_lazy is None:
            self._client_lazy = get_client()
        return self._client_lazy

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
        prior_production_note: str | None = None,
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
            "prior_production_note": prior_production_note,
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
        drift_7d: float | None = None,
        last_change_at: datetime | None = None,
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
        # Optional (DATA_MODEL.md §6): every caller before Phase 7.2 only ever computed
        # a bare `reality_drift` (hardcoded 0.0, no cycle-to-cycle history existed yet
        # to derive a 7-day window or a last-change timestamp from) — reverify_worker is
        # the first caller with real `DriftResult` data to report.
        if drift_7d is not None:
            data["drift_7d"] = drift_7d
        if last_change_at is not None:
            data["last_change_at"] = last_change_at
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
        delta: dict[str, dict[str, object]] | None = None,
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

    def get_project_summary(self, project_id: str) -> dict[str, object] | None:
        """PHASE_08.md §8.1's metrics endpoint reads the already-computed
        `project_summary` doc rather than recomputing drift/counts from Cloud SQL —
        that logic already lives in `reverify_worker`/`services/ingest`, the only two
        real writers of this doc; a second, independent computation here would just be
        a second place for the two to drift apart."""
        doc = self._client.collection("projects").document(project_id).get()
        return doc.to_dict() if doc.exists else None

    def list_events(
        self, project_id: str, *, limit: int = 50, before: datetime | None = None
    ) -> list[dict[str, object]]:
        """Paged, newest-first (PHASE_08.md §8.1's events feed). `before` is the `at`
        timestamp of the last item on the previous page — Firestore's own natural
        cursor, no separate offset/token bookkeeping needed."""
        query = (
            self._client.collection("projects")
            .document(project_id)
            .collection("events")
            .order_by("at", direction=firestore.Query.DESCENDING)
        )
        if before is not None:
            query = query.where("at", "<", before)
        return [dict(doc.to_dict() or {}, event_id=doc.id) for doc in query.limit(limit).stream()]
