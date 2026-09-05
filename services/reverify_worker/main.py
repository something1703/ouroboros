"""services/reverify_worker — Cloud Run, Pub/Sub push (`sa-reverify`, real Cloud SQL/VPC
access, unlike the Agent Engine's own runtime — docs/DECISIONS.md #062). Chains
re-verification Task runs, recomputes risk and Reality Drift, posts Slack on risk
changes. PHASE_07.md §7.2, ARCHITECTURE.md §2.5.

Two event shapes arrive here (both via `verification.events`, published by
`webhook_receiver`):
- `monitor.event.detected` — Parallel detected a change on a Monitor. Starts a new,
  chained Task run (`previous_interaction_id`) and returns; the *result* arrives later
  as a second, separate `task_run.status` event.
- `task_run.status` (`is_active=False`) — the chained Task run above finished. Fetches
  its result, writes Evidence, re-scores risk, recomputes drift, alerts.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import FastAPI, Request, Response
from google import genai
from google.genai import types
from pydantic import BaseModel

from config.parallel import MIN_REVERIFY_COOLDOWN_HOURS
from packages.claims.drift import ClaimDriftInput, reality_drift
from packages.claims.enums import ClaimCategory, RiskLevel, VerificationStatus
from packages.claims.models import Claim, Evidence, Risk, VerificationEvent
from packages.claims.risk import prescore
from packages.common.errors import BudgetExceeded
from packages.common.ids import new_ulid
from packages.common.logging import get_logger
from packages.common.slack import post_risk_change_alert
from packages.common.tracing import configure_tracing, flush_tracing, instrument_fastapi, span
from packages.ledger.db import session_scope
from packages.ledger.projections import Projector
from packages.ledger.repositories import (
    ClaimRepo,
    EvidenceRepo,
    HistoryRepo,
    ProjectRepo,
    RiskRepo,
    record_evidence_and_status,
)
from packages.parallel_client.cost import CostMeter, check_budget
from packages.parallel_client.monitor import events as monitor_events
from packages.parallel_client.task import build_input, fetch_result
from packages.parallel_client.task import run as run_task
from packages.parallel_client.webhooks import MonitorEventDetected, TaskRunStatusEvent, parse_event

configure_tracing(service="reverify_worker")

app = FastAPI()
instrument_fastapi(app)
log = get_logger(__name__)

_projector = Projector()

# Which Parallel spec re-verifies a claim, by its own category — matches exactly what
# each category's original specialist/agent used to verify it the first time
# (agents/ouroboros/clear/{music,brand,person,location_art}.py,
# agents/ouroboros/truecut/{fact,archive}.py). `quote` has no entry: a real,
# pre-existing gap with no specialist agent at all (docs/DECISIONS.md #088) — a
# `quote` claim is simply never re-verified here either, same limitation.
_SPEC_BY_CATEGORY: dict[ClaimCategory, str] = {
    ClaimCategory.MUSIC: "legal_music",
    ClaimCategory.BRAND: "legal_brand",
    ClaimCategory.PERSON: "legal_person",
    ClaimCategory.LOCATION: "legal_location_artwork",
    ClaimCategory.ARTWORK: "legal_location_artwork",
    ClaimCategory.ARCHIVAL: "legal_location_artwork",
    ClaimCategory.IDENTITY: "legal_location_artwork",
    ClaimCategory.EVENT: "factual_claim",
    ClaimCategory.STATISTIC: "factual_claim",
    ClaimCategory.ATTRIBUTION: "factual_claim",
}

# DATA_MODEL.md §6: "changed = 1 if the latest cycle's (verdict|holder|confidence|
# risk_level) differs from the previous cycle's". Evidence.output's exact keys vary by
# spec (a legal spec has rights-holder-shaped fields; a factual spec has `verdict`), so
# this checks every known headline field name rather than assuming one schema.
_HEADLINE_FIELDS = (
    "verdict",
    "rights_holder",
    "artwork_rights_holder",
    "owner_or_custodian",
    "composition_rights_holder",
    "master_rights_holder",
    "estate_or_representation",
)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {"ok": True, "service": "reverify_worker"}


@app.post("/pubsub/verification")
async def handle_verification_event(request: Request) -> Response:
    envelope = await request.json()
    data_b64 = envelope.get("message", {}).get("data", "")
    payload = json.loads(base64.b64decode(data_b64).decode("utf-8")) if data_b64 else {}

    try:
        event = parse_event(payload)
    except ValueError as exc:
        log.warning("reverify_unrecognized_event", error=str(exc))
        return Response(status_code=200)  # ack — Pub/Sub redelivery won't fix a bad payload

    with span("reverify", event_type=event.type):
        try:
            if isinstance(event, MonitorEventDetected):
                _handle_monitor_event(event)
            else:
                _handle_task_completion(event)
        except BudgetExceeded as exc:
            log.warning("reverify_budget_exceeded", error=str(exc))
        except Exception:
            log.exception("reverify_event_failed", event_type=event.type)
            flush_tracing()
            # A transient failure (a real one -- network blip, a momentary Cloud SQL
            # hiccup) should be retried by Pub/Sub, not silently acked into oblivion.
            return Response(status_code=500)

    flush_tracing()
    return Response(status_code=200)


def _handle_monitor_event(event: MonitorEventDetected) -> None:
    """Starts a new, chained Task run. Does not write Evidence itself -- that only
    happens once the chained run's own `task_run.status` event arrives later
    (`_handle_task_completion`); this half just kicks it off and marks the claim
    `stale` in the meantime, per PHASE_07.md §7.2."""
    claim_id = event.metadata.get("claim_id", "")
    project_id = event.metadata.get("project_id", "")
    if not claim_id or not project_id:
        log.warning("reverify_monitor_event_missing_metadata", metadata=event.metadata)
        return

    with session_scope() as session:
        claim = ClaimRepo.require(session, claim_id)
        check_budget(session, project_id)

        if not _cooldown_elapsed(session, claim_id):
            log.info("reverify_skipped_cooldown", claim_id=claim_id)
            return

        spec = _SPEC_BY_CATEGORY.get(claim.category)
        if spec is None:
            log.warning("reverify_no_spec_for_category", claim_id=claim_id, category=claim.category)
            return

        raw_events = monitor_events(event.monitor_id, event_group_id=event.event_group_id)
        summary = "; ".join(e.event_type for e in raw_events) or "monitor event detected"
        event_id = new_ulid()
        _projector.event_entry(
            project_id,
            event_id=event_id,
            at=datetime.now(UTC),
            claim_id=claim_id,
            kind="monitor_event",
            summary=summary,
        )

        latest_evidence = EvidenceRepo.latest_for_claim(session, claim_id)
        # `previous_interaction_id` chains this new Task run to the claim's own most
        # recent one (Parallel's continuation semantics -- carries prior citations/
        # context forward), not the monitor event's own id: the event has no run-like
        # identity of its own to continue from, only the claim's evidence trail does.
        previous_interaction_id = latest_evidence.parallel_run_id if latest_evidence else None
        next_cycle = EvidenceRepo.next_cycle(session, claim_id)

        with CostMeter(session, project_id, api="task", sku="task.core-fast", claim_id=claim_id):
            pass  # budget-reserve only; the real call happens after this transaction commits

        ClaimRepo.set_status(session, claim_id, VerificationStatus.STALE)
        HistoryRepo.append(
            session,
            VerificationEvent(
                claim_id=claim_id,
                at=datetime.now(UTC),
                actor="reverify_worker",
                from_status=claim.status,
                to_status=VerificationStatus.STALE,
                note=f"monitor event detected: {summary}",
                ref={"monitor_id": event.monitor_id, "event_id": event_id},
            ),
        )

    task_input = build_input(
        claim.claim_text,
        jurisdictions=claim.jurisdictions,
        excerpt=claim.source.excerpt,
        top_urls=[],
    )
    run_task(
        task_input,
        spec,
        claim_id=claim_id,
        project_id=project_id,
        cycle=next_cycle,
        processor="core-fast",
        previous_interaction_id=previous_interaction_id,
        memory_scope_key=claim.studio_id,
        wait=False,
    )
    log.info("reverify_task_started", claim_id=claim_id, cycle=next_cycle)


def _handle_task_completion(event: TaskRunStatusEvent) -> None:
    if event.is_active:
        return  # still running; nothing to do until the terminal event arrives
    claim_id = event.metadata.get("claim_id", "")
    project_id = event.metadata.get("project_id", "")
    spec = event.metadata.get("spec", "")
    cycle_str = event.metadata.get("cycle", "")
    if not claim_id or not project_id or not spec:
        log.warning("reverify_task_event_missing_metadata", metadata=event.metadata)
        return
    cycle = int(cycle_str) if cycle_str.isdigit() else 1

    if event.error_message:
        _record_task_failure(claim_id, event.run_id, event.error_message)
        return

    result = fetch_result(event.run_id, spec=spec, claim_id=claim_id)
    content: dict[str, object] = (
        result.content if isinstance(result.content, dict) else {"text": result.content}
    )

    with session_scope() as session:
        claim = ClaimRepo.require(session, claim_id)
        prior_risk = RiskRepo.get(session, claim_id)
        prior_output = _prior_evidence_output(session, claim_id)

        evidence = Evidence(
            claim_id=claim_id,
            cycle=cycle,
            method="task",
            parallel_run_id=result.run_id,
            processor=result.processor,
            output=content,
            basis=result.basis,
            overall_confidence=result.overall_confidence,
            cost_usd=Decimal("0"),  # already reserved via CostMeter when the run started
            created_at=datetime.now(UTC),
        )
        record_evidence_and_status(
            session,
            evidence=evidence,
            event=VerificationEvent(
                claim_id=claim_id,
                at=datetime.now(UTC),
                actor="reverify_worker",
                from_status=claim.status,
                to_status=VerificationStatus.VERIFIED,
                note=f"re-verified (cycle {cycle}) via {result.processor}",
                ref={"run_id": result.run_id},
            ),
            new_status=VerificationStatus.VERIFIED,
        )

        changed = _content_changed(prior_output, content)
        risk = _score_risk(evidence, claim)
        RiskRepo.upsert(session, risk)

        delta = _compute_delta(prior_output, content, prior_risk, risk)
        _projector.event_entry(
            project_id,
            event_id=new_ulid(),
            at=datetime.now(UTC),
            claim_id=claim_id,
            kind="risk_changed" if changed else "reverified",
            summary=f"re-verified: {risk.level.value} ({risk.rationale})",
            delta=delta,
        )

        drift_inputs = _project_drift_inputs(session, project_id, claim_id, risk.level, changed)
        counts_by_status = ClaimRepo.count_by_status(session, project_id)
        counts_by_risk = RiskRepo.count_by_level(session, project_id)
        spend_usd = ProjectRepo.spend(session, project_id)
        project = ProjectRepo.require(session, project_id)

    drift = reality_drift(drift_inputs)
    _projector.claim_view(
        project_id=project_id,
        claim_id=claim_id,
        category=claim.category.value,
        entity_text=claim.entity_text,
        claim_text=claim.claim_text,
        priority=claim.priority,
        status=VerificationStatus.VERIFIED.value,
        updated_at=datetime.now(UTC),
        risk_level=risk.level.value,
        risk_score=risk.score,
        evidence_summary=content,
        history_count=cycle,
        monitor_status="active",
        prior_production_note=claim.prior_production_note,
    )
    _projector.project_summary(
        project_id,
        title=project.title,
        release_date=project.release_date,
        counts_by_status=counts_by_status,
        counts_by_risk=counts_by_risk,
        reality_drift=drift.drift,
        drift_7d=drift.drift_7d,
        last_change_at=drift.last_change_at,
        spend_usd=spend_usd,
    )

    log.info(
        "reverify_complete",
        claim_id=claim_id,
        cycle=cycle,
        risk_level=risk.level.value,
        changed=changed,
        drift=drift.drift,
    )

    if changed and risk.level in (RiskLevel.HIGH, RiskLevel.BLOCKING):
        try:
            post_risk_change_alert(
                project_id=project_id,
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                risk_level=risk.level.value,
                rationale=risk.rationale,
                delta=delta,
                top_citation=result.basis[0].citations[0].url
                if result.basis and result.basis[0].citations
                else None,
            )
        except Exception as exc:
            log.warning("reverify_slack_alert_failed", claim_id=claim_id, error=str(exc))


def _record_task_failure(claim_id: str, run_id: str, error_message: str) -> None:
    with session_scope() as session:
        claim = ClaimRepo.require(session, claim_id)
        ClaimRepo.set_status(session, claim_id, VerificationStatus.ERROR)
        HistoryRepo.append(
            session,
            VerificationEvent(
                claim_id=claim_id,
                at=datetime.now(UTC),
                actor="reverify_worker",
                from_status=claim.status,
                to_status=VerificationStatus.ERROR,
                note=f"re-verification Task run failed: {error_message[:500]}",
                ref={"run_id": run_id},
            ),
        )
    log.error("reverify_task_failed", claim_id=claim_id, error=error_message)


def _cooldown_elapsed(session: object, claim_id: str) -> bool:
    """PHASE_07.md's own risk section: 'no re-verify more than once per 6h' --
    `MIN_REVERIFY_COOLDOWN_HOURS`, config/parallel.py."""
    latest = EvidenceRepo.latest_for_claim(session, claim_id)  # type: ignore[arg-type]
    if latest is None:
        return True
    elapsed = datetime.now(UTC) - latest.created_at
    return elapsed.total_seconds() >= MIN_REVERIFY_COOLDOWN_HOURS * 3600


def _prior_evidence_output(session: object, claim_id: str) -> dict[str, object] | None:
    latest = EvidenceRepo.latest_for_claim(session, claim_id)  # type: ignore[arg-type]
    return latest.output if latest else None


def _content_changed(prior: dict[str, object] | None, new: dict[str, object]) -> bool:
    if prior is None:
        return True  # first-ever cycle always counts as a change
    return any(prior.get(field) != new.get(field) for field in _HEADLINE_FIELDS)


def _compute_delta(
    prior: dict[str, object] | None, new: dict[str, object], prior_risk: Risk | None, risk: Risk
) -> dict[str, dict[str, object]]:
    delta: dict[str, dict[str, object]] = {}
    for field in _HEADLINE_FIELDS:
        prior_value = prior.get(field) if prior else None
        new_value = new.get(field)
        if prior_value != new_value:
            delta[field] = {"from": prior_value, "to": new_value}
    if prior_risk is not None and prior_risk.level != risk.level:
        delta["risk_level"] = {"from": prior_risk.level.value, "to": risk.level.value}
    return delta


def _project_drift_inputs(
    session: object,
    project_id: str,
    changed_claim_id: str,
    changed_level: RiskLevel,
    changed: bool,
) -> list[ClaimDriftInput]:
    """Every OTHER claim's risk hasn't moved since its own last assessment -- only the
    claim this event just re-verified can be `changed` this round. `RiskRow.assessed_at`
    stands in for 'latest cycle at' (risk is reassessed alongside every new Evidence
    cycle in this system, so the two times track closely) -- see
    packages/ledger/repositories.py::RiskRepo.list_assessed_at_by_project."""
    now = datetime.now(UTC)
    rows = RiskRepo.list_assessed_at_by_project(session, project_id)  # type: ignore[arg-type]
    inputs = []
    found_changed_claim = False
    for claim_id, level, assessed_at in rows:
        is_changed_claim = claim_id == changed_claim_id
        found_changed_claim = found_changed_claim or is_changed_claim
        at = assessed_at if assessed_at.tzinfo else assessed_at.replace(tzinfo=UTC)
        inputs.append(
            ClaimDriftInput(
                claim_id=claim_id,
                risk_level=RiskLevel(level),
                changed=changed if is_changed_claim else False,
                latest_cycle_at=at,
            )
        )
    if not found_changed_claim:
        inputs.append(
            ClaimDriftInput(
                claim_id=changed_claim_id,
                risk_level=changed_level,
                changed=changed,
                latest_cycle_at=now,
            )
        )
    return inputs


class _RiskAdjustment(BaseModel):
    level: RiskLevel
    score: float
    rationale: str
    remediation_suggested: bool
    remediation_kind: str


def _score_risk(evidence: Evidence, claim: Claim) -> Risk:
    """Deterministic pre-score, then a real but lightweight Gemini call (no ADK, no
    tools -- PHASE_07.md §7.2: 'not a full Agent Engine run') that may adjust it ±1
    level with a written rationale, mirroring RiskAssessor's own rubric
    (agents/ouroboros/prompts/risk_assessor.md) at a fraction of the cost/latency."""
    level, score, rationale = prescore(evidence, claim)
    adjustment = _adjust_risk_with_gemini(level, score, rationale, evidence, claim)
    return Risk(
        claim_id=evidence.claim_id,
        evidence_id=evidence.evidence_id,
        level=adjustment.level if adjustment else level,
        score=adjustment.score if adjustment else score,
        rationale=adjustment.rationale if adjustment else "; ".join(rationale),
        remediation_suggested=adjustment.remediation_suggested if adjustment else False,
        remediation_kind=adjustment.remediation_kind if adjustment else "none",
        assessed_at=datetime.now(UTC),
    )


def _adjust_risk_with_gemini(
    level: RiskLevel, score: float, rationale: list[str], evidence: Evidence, claim: Claim
) -> _RiskAdjustment | None:
    prompt = (
        "You are re-scoring risk for one already-verified claim after re-verification. "
        f"Claim kind: {claim.kind.value}, category: {claim.category.value}, "
        f"priority: {claim.priority}.\n"
        f"Deterministic pre-score: level={level.value}, score={score}, "
        f"rationale={'; '.join(rationale)}.\n"
        f"Latest evidence (confidence={evidence.overall_confidence.value}): "
        f"{json.dumps(evidence.output)[:4000]}\n"
        "Confirm the pre-score, or adjust by at most one level "
        "(blocking > high > medium > low > none) with a one-sentence rationale explaining "
        "why. Set remediation_suggested=true and an appropriate remediation_kind only if "
        "the final level is high or blocking."
    )
    try:
        client = genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RiskAdjustment,
                temperature=0.3,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            return None
        return (
            parsed
            if isinstance(parsed, _RiskAdjustment)
            else _RiskAdjustment.model_validate(parsed)
        )
    except Exception as exc:
        log.warning("reverify_risk_adjustment_failed", error=str(exc))
        return None
