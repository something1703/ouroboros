"""services/dashboard_api — Cloud Run, FastAPI. Thin ingest-facing slice for Phase 3
(PHASE_03.md §3.6): signed-URL asset upload, asset listing, claim listing. Phase 5.5
adds run-triggering: `POST /projects/{id}/runs` (human/API-triggered) and
`POST /internal/runs/auto` (a Pub/Sub push target on `claims.extracted`, gated by the
`AUTO_RUN_AFTER_INGEST` feature flag). Broader dashboard endpoints (evidence, exports,
Ask Ouroboros) land in later phases per services/dashboard_api/README.md.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Literal

import google.auth
import google.auth.transport.requests as gauth_requests
import google.cloud.storage as storage
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.parallel import days_to_release, frequency_for
from packages.claims.enums import ClaimCategory, RiskLevel, VerificationStatus
from packages.claims.models import Asset, Claim, Evidence, Project, Risk, Segment, VerificationEvent
from packages.common.errors import Conflict, NotFound
from packages.common.logging import get_logger
from packages.common.tracing import configure_tracing, flush_tracing, instrument_fastapi
from packages.exports.clearance_sheet import export_clearance_sheet
from packages.exports.eo_pdf import generate_eo_pack
from packages.exports.factcheck_pdf import generate_factcheck_report
from packages.ledger.db import session_scope
from packages.ledger.projections import Projector
from packages.ledger.repositories import (
    AssetRepo,
    ClaimRepo,
    EvidenceRepo,
    HistoryRepo,
    MonitorRepo,
    ProjectRepo,
    RiskRepo,
)
from packages.parallel_client.monitor import trigger as monitor_trigger
from packages.parallel_client.monitor import update as monitor_update

from .auth import UserContext, get_current_user, require_internal_caller
from .runs import ask_question, start_run

configure_tracing(service="dashboard_api")
log = get_logger(__name__)

app = FastAPI(title="Ouroboros Dashboard API")
instrument_fastapi(app)


@app.middleware("http")
async def _flush_tracing_after_response(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # PHASE_09.md §9.4: found live -- unlike ingest/webhook_receiver/reverify_worker
    # (each a single message-handler that already calls flush_tracing() once at the
    # end), dashboard_api has many endpoints and never called it anywhere, so every
    # one of its spans (FastAPIInstrumentor auto-instruments every request) was
    # silently dropped by Cloud Run's CPU-freeze-between-requests behavior
    # (packages/common/tracing.py::flush_tracing's own docstring) -- confirmed by a
    # real Cloud Trace query over this project returning zero traces despite heavy
    # real dashboard_api traffic all session. A middleware covers every route in one
    # place instead of adding a call to each handler individually.
    response = await call_next(request)
    flush_tracing()
    return response


# Phase 8.2: web/ calls this API from a different origin (localhost:5173 in dev, the
# deployed web app's own origin once known) -- browsers block that without CORS
# headers, found live while researching the frontend build (no CORSMiddleware existed
# anywhere in this codebase before now). Empty-until-set, same pattern as
# GOOGLE_OAUTH_CLIENT_ID: comma-separated origins, no wildcard (credentialed requests
# -- the GIS bearer token -- can't use `allow_origins=["*"]` per the CORS spec anyway).
_cors_origins = [o for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

_projector = Projector()

UPLOAD_URL_TTL = timedelta(minutes=15)
PLAYBACK_URL_TTL = timedelta(hours=1)
_CUT_SUFFIXES = {"mp4", "mov"}
_EVENTS_PAGE_LIMIT = 50


class ClaimWithRisk(Claim):
    """`Claim` plus its current risk level, for a project-wide worklist ranked by
    risk (PHASE_08.md §8.2's "Needs attention" redesign) -- `Claim` alone has no risk
    field (`Risk` is a separate per-claim row, DATA_MODEL.md §3), and this endpoint's
    callers need it without an N+1 round trip per claim."""

    risk_level: RiskLevel | None = None


class UploadRequest(BaseModel):
    kind: Literal["script", "cut"]
    filename: str


class UploadResponse(BaseModel):
    upload_url: str
    gcs_uri: str


class StartRunRequest(BaseModel):
    asset_id: str
    mode: Literal["clear", "truecut", "ask"] = "clear"


class StartRunResponse(BaseModel):
    run_id: str


class TimelineClaim(BaseModel):
    """One claim positioned on an asset's timeline (PHASE_06.md §6.4). `t_start_ms`/
    `t_end_ms`/`channel` are null for a script-asset claim (page-based, not time-based)
    — the UI's video scrubber only ever plots claims that have them."""

    claim_id: str
    kind: str
    category: str
    claim_text: str
    page: int | None
    t_start_ms: int | None
    t_end_ms: int | None
    channel: str | None
    status: str
    verdict: str | None
    risk_level: str | None
    top_citation: str | None


class TimelineResponse(BaseModel):
    asset_id: str
    duration_ms: int | None
    segments: list[Segment]
    claims: list[TimelineClaim]


class SegmentsResponse(BaseModel):
    asset_id: str
    segments: list[Segment]


class PlaybackResponse(BaseModel):
    proxy_url: str | None
    poster_url: str | None


class FileUrlResponse(BaseModel):
    url: str


class PublicShowcaseMetrics(BaseModel):
    """A deliberately narrow, unauthenticated subset of `MetricsResponse` for the
    public marketing site's "live proof" section (PRODUCT.md Principle 4: real data
    over mocked). Scoped to one configured demo project only, and to only the fields
    safe to show a stranger -- no spend, no claim counts, no project identity beyond
    what `PUBLIC_SHOWCASE_PROJECT_ID` already names in this file."""

    reality_drift: float | None
    drift_7d: float | None
    current_cadence: str


class CreateProjectRequest(BaseModel):
    project_id: str
    studio_id: str
    title: str
    release_date: str | None = None  # ISO date, e.g. "2026-10-10"
    shooting_countries: list[str] = []
    distribution_territories: list[str] = []
    budget_cap_usd: float = 10.0


class ClaimDetail(BaseModel):
    """PHASE_08.md §8.1: a claim's full evidence history + risk + verification
    history, for the claim drawer — one round trip instead of four."""

    claim: Claim
    evidence_history: list[Evidence]
    risk: Risk | None
    history: list[VerificationEvent]
    monitor_status: str | None


class HumanOverrideRequest(BaseModel):
    """PATCH body for a human overriding a claim's status and/or risk level, with a
    required note recorded into `verification_history` (`actor="human"`)."""

    status: VerificationStatus | None = None
    risk_level: RiskLevel | None = None
    note: str


class EventsFeedResponse(BaseModel):
    events: list[dict[str, object]]
    next_before: str | None  # pass back as `?before=` to fetch the next page


class MetricsResponse(BaseModel):
    reality_drift: float | None
    drift_7d: float | None
    last_change_at: datetime | None
    spend_usd: float | None
    counts_by_status: dict[str, int]
    counts_by_risk: dict[str, int]
    days_to_release: int
    current_cadence: str


class TriggerAllResponse(BaseModel):
    total: int
    triggered: int
    errors: list[dict[str, str]]


class AskRequest(BaseModel):
    question: str
    asset_id: str = ""


class AskResponse(BaseModel):
    answer: str


class ExportResponse(BaseModel):
    url: str


EXPORT_URL_TTL = timedelta(hours=1)


@app.exception_handler(NotFound)
def _not_found_handler(_request: Request, exc: NotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(Conflict)
def _conflict_handler(_request: Request, exc: Conflict) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/status")
def status() -> dict[str, object]:
    return {"ok": True, "service": "dashboard_api"}


@app.get("/me", response_model=UserContext)
def get_me(user: UserContext = Depends(get_current_user)) -> UserContext:
    """Phase 8.2: the web app's own role banner and role-gated quick actions need to
    know the signed-in caller's role without piggybacking on a business endpoint."""
    return user


@app.post("/projects/{project_id}/assets", response_model=UploadResponse)
def create_upload_url(
    project_id: str, body: UploadRequest, _user: UserContext = Depends(get_current_user)
) -> UploadResponse:
    with session_scope() as session:
        ProjectRepo.require(session, project_id)

    object_name = _object_name(project_id, kind=body.kind, filename=body.filename)
    bucket = os.environ["INTAKE_BUCKET"]
    upload_url = _generate_upload_url(bucket, object_name)
    return UploadResponse(upload_url=upload_url, gcs_uri=f"gs://{bucket}/{object_name}")


@app.get("/projects/{project_id}/assets", response_model=list[Asset])
def list_assets(project_id: str, _user: UserContext = Depends(get_current_user)) -> list[Asset]:
    with session_scope() as session:
        ProjectRepo.require(session, project_id)
        return AssetRepo.list_by_project(session, project_id)


@app.get("/projects/{project_id}/claims", response_model=list[ClaimWithRisk])
def list_claims(
    project_id: str,
    status: VerificationStatus | None = Query(default=None),
    category: ClaimCategory | None = Query(default=None),
    _user: UserContext = Depends(get_current_user),
) -> list[ClaimWithRisk]:
    with session_scope() as session:
        ProjectRepo.require(session, project_id)
        claims = ClaimRepo.list_by_project(
            session, project_id, status=status, category=category.value if category else None
        )
        risk_by_claim = {
            claim_id: RiskLevel(level)
            for claim_id, level, _assessed_at in RiskRepo.list_assessed_at_by_project(
                session, project_id
            )
        }
    return [
        ClaimWithRisk(**claim.model_dump(), risk_level=risk_by_claim.get(claim.claim_id))
        for claim in claims
    ]


@app.get("/projects", response_model=list[Project])
def list_projects(_user: UserContext = Depends(get_current_user)) -> list[Project]:
    with session_scope() as session:
        return ProjectRepo.list_all(session)


@app.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str, _user: UserContext = Depends(get_current_user)) -> Project:
    with session_scope() as session:
        return ProjectRepo.require(session, project_id)


@app.post("/projects", response_model=Project, status_code=201)
def create_project(
    body: CreateProjectRequest, _user: UserContext = Depends(get_current_user)
) -> Project:
    project = Project(
        project_id=body.project_id,
        studio_id=body.studio_id,
        title=body.title,
        release_date=date.fromisoformat(body.release_date) if body.release_date else None,
        shooting_countries=body.shooting_countries,
        distribution_territories=body.distribution_territories,
        budget_cap_usd=body.budget_cap_usd,
        created_at=datetime.now(UTC),
    )
    with session_scope() as session:
        ProjectRepo.create(session, project)
    return project


@app.get("/projects/{project_id}/claims/{claim_id}", response_model=ClaimDetail)
def get_claim_detail(
    project_id: str, claim_id: str, _user: UserContext = Depends(get_current_user)
) -> ClaimDetail:
    with session_scope() as session:
        ProjectRepo.require(session, project_id)
        claim = ClaimRepo.require(session, claim_id)
        if claim.project_id != project_id:
            raise NotFound("claim", claim_id)
        monitor = MonitorRepo.get_by_claim(session, claim_id)
        return ClaimDetail(
            claim=claim,
            evidence_history=EvidenceRepo.history_for_claim(session, claim_id),
            risk=RiskRepo.get(session, claim_id),
            monitor_status=monitor.status if monitor else None,
            history=HistoryRepo.for_claim(session, claim_id),
        )


@app.patch("/projects/{project_id}/claims/{claim_id}", response_model=ClaimDetail)
def override_claim(
    project_id: str,
    claim_id: str,
    body: HumanOverrideRequest,
    user: UserContext = Depends(get_current_user),
) -> ClaimDetail:
    if body.status is None and body.risk_level is None:
        raise HTTPException(422, "must override at least one of status/risk_level")

    with session_scope() as session:
        ProjectRepo.require(session, project_id)
        claim = ClaimRepo.require(session, claim_id)
        if claim.project_id != project_id:
            raise NotFound("claim", claim_id)
        _require_override_role(user, claim.kind.value)

        now = datetime.now(UTC)
        if body.status is not None:
            HistoryRepo.append(
                session,
                VerificationEvent(
                    claim_id=claim_id,
                    at=now,
                    actor="human",
                    from_status=claim.status,
                    to_status=body.status,
                    note=body.note,
                    ref={"user": user.email},
                ),
            )
            ClaimRepo.set_status(session, claim_id, body.status)

        if body.risk_level is not None:
            existing_risk = RiskRepo.get(session, claim_id)
            if existing_risk is None:
                raise HTTPException(409, "claim has no assessed risk yet to override")
            RiskRepo.upsert(
                session,
                existing_risk.model_copy(
                    update={
                        "level": body.risk_level,
                        "rationale": f"Human override by {user.email}: {body.note}",
                        "assessed_at": now,
                    }
                ),
            )
            HistoryRepo.append(
                session,
                VerificationEvent(
                    claim_id=claim_id,
                    at=now,
                    actor="human",
                    from_status=body.status or claim.status,
                    to_status=body.status or claim.status,
                    note=f"risk override: {existing_risk.level.value} -> {body.risk_level.value}. {body.note}",
                    ref={"user": user.email, "override": "risk"},
                ),
            )

        updated_claim = ClaimRepo.require(session, claim_id)
        evidence_history = EvidenceRepo.history_for_claim(session, claim_id)
        risk = RiskRepo.get(session, claim_id)
        history = HistoryRepo.for_claim(session, claim_id)
        monitor = MonitorRepo.get_by_claim(session, claim_id)

    _projector.claim_view(
        project_id=project_id,
        claim_id=claim_id,
        category=updated_claim.category.value,
        entity_text=updated_claim.entity_text,
        claim_text=updated_claim.claim_text,
        priority=updated_claim.priority,
        status=updated_claim.status.value,
        updated_at=now,
        risk_level=risk.level.value if risk else None,
        risk_score=risk.score if risk else None,
        evidence_summary=_evidence_summary(evidence_history[-1] if evidence_history else None),
        history_count=len(history),
        monitor_status=monitor.status if monitor else None,
        prior_production_note=updated_claim.prior_production_note,
    )
    return ClaimDetail(
        claim=updated_claim,
        evidence_history=evidence_history,
        risk=risk,
        history=history,
        monitor_status=monitor.status if monitor else None,
    )


@app.get("/projects/{project_id}/events", response_model=EventsFeedResponse)
def list_events(
    project_id: str,
    before: datetime | None = Query(default=None),
    _user: UserContext = Depends(get_current_user),
) -> EventsFeedResponse:
    with session_scope() as session:
        ProjectRepo.require(session, project_id)
    events = _projector.list_events(project_id, limit=_EVENTS_PAGE_LIMIT, before=before)
    next_before = str(events[-1]["at"]) if len(events) == _EVENTS_PAGE_LIMIT else None
    return EventsFeedResponse(events=events, next_before=next_before)


@app.get("/projects/{project_id}/metrics", response_model=MetricsResponse)
def get_metrics(project_id: str, _user: UserContext = Depends(get_current_user)) -> MetricsResponse:
    with session_scope() as session:
        project = ProjectRepo.require(session, project_id)
    summary = _projector.get_project_summary(project_id) or {}
    days_left = days_to_release(project.release_date)
    return MetricsResponse(
        reality_drift=summary.get("reality_drift"),
        drift_7d=summary.get("drift_7d"),
        last_change_at=summary.get("last_change_at"),
        spend_usd=summary.get("spend_usd"),
        counts_by_status=summary.get("counts_by_status") or {},
        counts_by_risk=summary.get("counts_by_risk") or {},
        days_to_release=days_left,
        current_cadence=frequency_for(days_left),
    )


@app.get("/public/showcase-metrics", response_model=PublicShowcaseMetrics)
def get_public_showcase_metrics() -> PublicShowcaseMetrics:
    """No auth by design -- the marketing site (`web/`'s public routes) reads this to
    show one real, live number instead of a fabricated one. Never add fields here
    without checking they're safe for a stranger to see (see the model's own
    docstring)."""
    project_id = os.environ.get("PUBLIC_SHOWCASE_PROJECT_ID", "demo")
    with session_scope() as session:
        project = ProjectRepo.get(session, project_id)
    if project is None:
        return PublicShowcaseMetrics(reality_drift=None, drift_7d=None, current_cadence="1w")
    summary = _projector.get_project_summary(project_id) or {}
    days_left = days_to_release(project.release_date)
    return PublicShowcaseMetrics(
        reality_drift=summary.get("reality_drift"),
        drift_7d=summary.get("drift_7d"),
        current_cadence=frequency_for(days_left),
    )


@app.post("/projects/{project_id}/monitors/trigger-all", response_model=TriggerAllResponse)
def trigger_all_monitors(
    project_id: str, _user: UserContext = Depends(get_current_user)
) -> TriggerAllResponse:
    """Phase 8.2's "Trigger monitors" quick action: unlike
    `/internal/jobs/trigger-monitor/{monitor_id}` (service-account-only, one specific
    monitor — PHASE_07.md §7.6's demo-forcing tool), this is GIS-gated and project-
    scoped, forcing every active Monitor in one project off-schedule at once, the
    shape an end user actually wants from a single button."""
    with session_scope() as session:
        ProjectRepo.require(session, project_id)
        monitors = [
            m for m, pid, _release_date in MonitorRepo.list_all_active(session) if pid == project_id
        ]

    triggered = 0
    errors: list[dict[str, str]] = []
    for monitor in monitors:
        try:
            monitor_trigger(monitor.monitor_id)
            triggered += 1
        except Exception as exc:
            log.warning("trigger_all_monitor_failed", monitor_id=monitor.monitor_id, error=str(exc))
            errors.append({"monitor_id": monitor.monitor_id, "error": str(exc)})

    return TriggerAllResponse(total=len(monitors), triggered=triggered, errors=errors)


def _require_override_role(user: UserContext, claim_kind: str) -> None:
    """`legal` overrides `kind=legal` claims, `editorial` overrides `kind=factual` ones
    (PHASE_08.md §8.1); `producer` is read-only and can never override either."""
    allowed = {"legal": "legal", "editorial": "factual"}.get(user.role)
    if allowed != claim_kind:
        raise HTTPException(403, f"role {user.role!r} cannot override a {claim_kind!r} claim")


def _evidence_summary(evidence: Evidence | None) -> dict[str, object] | None:
    if evidence is None:
        return None
    top_citations = []
    for field_basis in evidence.basis[:3]:
        if field_basis.citations:
            top_citations.append(field_basis.citations[0].url)
    return {
        "method": evidence.method,
        "confidence": evidence.overall_confidence.value,
        "cycle": evidence.cycle,
        "top_citations": top_citations,
    }


@app.get("/assets/{asset_id}/timeline", response_model=TimelineResponse)
def get_asset_timeline(
    asset_id: str, _user: UserContext = Depends(get_current_user)
) -> TimelineResponse:
    """PHASE_06.md §6.4: segments + every claim sourced from this asset, each with its
    latest verdict/risk/top citation so the UI can plot a scrubber without a second
    round trip per claim."""
    with session_scope() as session:
        asset = AssetRepo.get(session, asset_id)
        if asset is None:
            raise NotFound("asset", asset_id)
        claims = ClaimRepo.list_by_asset(session, asset_id)
        timeline_claims = [_timeline_claim(session, claim) for claim in claims]
    # Video (cut) claims sort by time; script claims have no t_start_ms and sort by
    # page instead -- a mixed sort key so either asset kind lands in reading order.
    timeline_claims.sort(
        key=lambda c: (c.t_start_ms is None, c.t_start_ms or 0, c.page is None, c.page or 0)
    )
    return TimelineResponse(
        asset_id=asset.asset_id,
        duration_ms=asset.duration_ms,
        segments=asset.segments,
        claims=timeline_claims,
    )


@app.get("/assets/{asset_id}/segments", response_model=SegmentsResponse)
def get_asset_segments(
    asset_id: str, _user: UserContext = Depends(get_current_user)
) -> SegmentsResponse:
    with session_scope() as session:
        asset = AssetRepo.get(session, asset_id)
        if asset is None:
            raise NotFound("asset", asset_id)
        return SegmentsResponse(asset_id=asset.asset_id, segments=asset.segments)


@app.get("/assets/{asset_id}/proxy", response_model=PlaybackResponse)
def get_asset_proxy(
    asset_id: str, _user: UserContext = Depends(get_current_user)
) -> PlaybackResponse:
    """PHASE_06.md §6.4: signed GET URLs for the low-res proxy MP4 + poster frame
    ffmpeg generated at ingest. Both fields are null (not a 404) for a script asset, or
    a cut asset ingested before this feature existed / without ARTIFACTS_BUCKET set."""
    with session_scope() as session:
        asset = AssetRepo.get(session, asset_id)
        if asset is None:
            raise NotFound("asset", asset_id)
    return PlaybackResponse(
        proxy_url=_generate_playback_url(asset.proxy_uri) if asset.proxy_uri else None,
        poster_url=_generate_playback_url(asset.poster_uri) if asset.poster_uri else None,
    )


@app.get("/assets/{asset_id}/file", response_model=FileUrlResponse)
def get_asset_file(
    asset_id: str, _user: UserContext = Depends(get_current_user)
) -> FileUrlResponse:
    """A signed GET URL for the asset's own originally-uploaded file (`gcs_uri`) --
    PHASE_08.md §8.3's script view needs the actual PDF to render with pdf.js, and
    unlike a cut's proxy/poster (transcoded, `get_asset_proxy`), a script asset has no
    separate viewable artifact: the uploaded PDF *is* the thing to display."""
    with session_scope() as session:
        asset = AssetRepo.get(session, asset_id)
        if asset is None:
            raise NotFound("asset", asset_id)
    return FileUrlResponse(url=_generate_playback_url(asset.gcs_uri))


def _timeline_claim(session: Session, claim: Claim) -> TimelineClaim:
    evidence = EvidenceRepo.latest_for_claim(session, claim.claim_id)
    risk = RiskRepo.get(session, claim.claim_id)
    verdict = None
    top_citation = None
    if evidence is not None:
        raw_verdict = evidence.output.get("verdict")
        verdict = str(raw_verdict) if raw_verdict is not None else None
        for field_basis in evidence.basis:
            if field_basis.citations:
                top_citation = field_basis.citations[0].url
                break
    return TimelineClaim(
        claim_id=claim.claim_id,
        kind=claim.kind.value,
        category=claim.category.value,
        claim_text=claim.claim_text,
        page=claim.source.page,
        t_start_ms=claim.source.t_start_ms,
        t_end_ms=claim.source.t_end_ms,
        channel=claim.source.channel,
        status=claim.status.value,
        verdict=verdict,
        risk_level=risk.level.value if risk else None,
        top_citation=top_citation,
    )


@app.post("/projects/{project_id}/runs", response_model=StartRunResponse)
async def create_run(
    project_id: str, body: StartRunRequest, user: UserContext = Depends(get_current_user)
) -> StartRunResponse:
    # Must be `async def`, not a plain sync handler -- found live: a sync FastAPI route
    # runs in Starlette's worker threadpool, not on the event loop thread, so
    # `start_run`'s internal `asyncio.create_task` had no running loop to attach to
    # ("RuntimeError: no running event loop"). An async handler runs directly on the
    # event loop, where create_task works as intended.
    #
    # Found live while wiring 8.2's "Run CLEAR"/"Run TRUE CUT" quick actions: this
    # route had no auth dependency at all, so once the service went
    # `--allow-unauthenticated` (docs/DECISIONS.md #107) anyone on the internet could
    # trigger a real, billed Agent Engine run. `producer` is read-only per PHASE_08.md
    # §8.2 (it can never override a claim either -- `_require_override_role`), so it's
    # blocked here too.
    if user.role == "producer":
        raise HTTPException(403, "role 'producer' cannot start a run")
    with session_scope() as session:
        ProjectRepo.require(session, project_id)
    run_id = start_run(project_id, body.asset_id, mode=body.mode)
    return StartRunResponse(run_id=run_id)


@app.post("/projects/{project_id}/ask", response_model=AskResponse)
def ask(
    project_id: str, body: AskRequest, _user: UserContext = Depends(get_current_user)
) -> AskResponse:
    """PHASE_08.md §8.4: the project page's chat drawer. Synchronous, unlike
    `/runs` (fire-and-forget with a polled `run_id`) -- the caller wants the actual
    answer in this one response. Open to every role (legal/editorial/producer):
    unlike overriding a claim or starting a run, asking a question is read-only."""
    with session_scope() as session:
        ProjectRepo.require(session, project_id)
    try:
        answer = ask_question(project_id, body.asset_id, body.question)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return AskResponse(answer=answer)


@app.post("/projects/{project_id}/exports/eo-pack", response_model=ExportResponse)
def export_eo_pack(
    project_id: str, _user: UserContext = Depends(get_current_user)
) -> ExportResponse:
    """PHASE_08.md §8.5: E&O evidence pack PDF. Open to every role (producer included --
    exports are read-only, not a business-state change like starting a run)."""
    with session_scope() as session:
        pdf_bytes = generate_eo_pack(session, project_id)
    url = _upload_export_pdf(project_id, "eo-pack.pdf", pdf_bytes)
    return ExportResponse(url=url)


@app.post("/projects/{project_id}/exports/factcheck-report", response_model=ExportResponse)
def export_factcheck_report(
    project_id: str, _user: UserContext = Depends(get_current_user)
) -> ExportResponse:
    """PHASE_08.md §8.5: timecode-ordered fact-check report PDF."""
    with session_scope() as session:
        pdf_bytes = generate_factcheck_report(session, project_id)
    url = _upload_export_pdf(project_id, "factcheck-report.pdf", pdf_bytes)
    return ExportResponse(url=url)


@app.post("/projects/{project_id}/exports/clearance-sheet", response_model=ExportResponse)
def export_clearance_log(
    project_id: str, _user: UserContext = Depends(get_current_user)
) -> ExportResponse:
    """PHASE_08.md §8.5: clearance log exported to a Google Sheet (idempotent --
    `packages/exports/clearance_sheet.py` updates the same sheet on repeat calls)."""
    with session_scope() as session:
        url = export_clearance_sheet(session, project_id)
    return ExportResponse(url=url)


def _upload_export_pdf(project_id: str, filename: str, pdf_bytes: bytes) -> str:
    bucket_name = os.environ.get(
        "ARTIFACTS_BUCKET", f"{os.environ['GOOGLE_CLOUD_PROJECT']}-artifacts-dev"
    )
    object_name = f"exports/{project_id}/{filename}"
    storage.Client().bucket(bucket_name).blob(object_name).upload_from_string(
        pdf_bytes, content_type="application/pdf"
    )
    return _generate_signed_url(bucket_name, object_name, method="GET", expiration=EXPORT_URL_TTL)


@app.post("/internal/runs/auto", dependencies=[Depends(require_internal_caller)])
async def auto_run(request: Request) -> dict[str, object]:
    """Pub/Sub push target on `claims.extracted` (infra/modules/pubsub — the
    subscription itself is added alongside this endpoint). Starts a CLEAR run
    automatically after ingest, only when `AUTO_RUN_AFTER_INGEST=true`; otherwise a
    no-op 200 (never a Pub/Sub-retry-triggering error) so the feature can be toggled
    without touching the subscription.

    Protected by `require_internal_caller`, not Cloud Run IAM (docs/DECISIONS.md):
    the whole service is now `--allow-unauthenticated` so real users' GIS tokens can
    reach `get_current_user` at all."""
    if os.environ.get("AUTO_RUN_AFTER_INGEST", "").lower() != "true":
        return {"skipped": True, "reason": "AUTO_RUN_AFTER_INGEST not enabled"}

    envelope = await request.json()
    data_b64 = envelope.get("message", {}).get("data", "")
    payload = json.loads(base64.b64decode(data_b64).decode("utf-8")) if data_b64 else {}
    project_id = payload.get("project_id")
    asset_id = payload.get("asset_id")
    if not project_id or not asset_id:
        log.warning("auto_run_bad_payload", payload=payload)
        return {"skipped": True, "reason": "missing project_id/asset_id"}

    run_id = start_run(project_id, asset_id, mode="clear")
    log.info("auto_run_started", project_id=project_id, asset_id=asset_id, run_id=run_id)
    return {"run_id": run_id}


@app.post("/internal/jobs/tighten", dependencies=[Depends(require_internal_caller)])
def tighten_monitors() -> dict[str, object]:
    """Cloud Scheduler daily target (PHASE_07.md §7.3): tightens every active Monitor's
    frequency as its project's release date approaches, and reconciles every Monitor's
    webhook URL to the real `webhook-receiver` service (PUBLIC_BASE_URL) — needed once,
    for real, for every Monitor created before that service existed (docs/DECISIONS.md
    #095), and cheap to keep doing unconditionally afterward since neither Parallel nor
    this ledger charges anything extra for an unchanged `monitor.update()` call.

    Protected by `require_internal_caller`, not Cloud Run IAM (docs/DECISIONS.md):
    the whole service is now `--allow-unauthenticated` so real users' GIS tokens can
    reach `get_current_user` at all."""
    webhook_base_url = os.environ.get("PUBLIC_BASE_URL", "")
    webhook_url = f"{webhook_base_url}/webhooks/parallel/monitor" if webhook_base_url else None

    with session_scope() as session:
        monitors = MonitorRepo.list_all_active(session)

    updated = 0
    unchanged = 0
    errors: list[dict[str, str]] = []
    for monitor, project_id, release_date in monitors:
        target_frequency = frequency_for(days_to_release(release_date))
        try:
            monitor_update(monitor.monitor_id, frequency=target_frequency, webhook_url=webhook_url)
        except Exception as exc:
            log.warning(
                "tighten_monitor_update_failed", monitor_id=monitor.monitor_id, error=str(exc)
            )
            errors.append({"monitor_id": monitor.monitor_id, "error": str(exc)})
            continue

        if target_frequency != monitor.frequency:
            with session_scope() as session:
                MonitorRepo.upsert(
                    session, monitor.model_copy(update={"frequency": target_frequency})
                )
            updated += 1
            log.info(
                "tighten_frequency_changed",
                monitor_id=monitor.monitor_id,
                project_id=project_id,
                old=monitor.frequency,
                new=target_frequency,
            )
        else:
            unchanged += 1

    return {"total": len(monitors), "updated": updated, "unchanged": unchanged, "errors": errors}


@app.post(
    "/internal/jobs/trigger-monitor/{monitor_id}", dependencies=[Depends(require_internal_caller)]
)
def trigger_monitor(monitor_id: str) -> dict[str, object]:
    """PHASE_07.md §7.6: forces an off-schedule Monitor run for the demo, instead of
    waiting for its own schedule (up to 1w for a freshly-created snapshot Monitor) to
    produce a real, organically-Parallel-issued webhook event. Per Parallel's own
    `monitor.trigger()` docs (see `packages/parallel_client/monitor.py`), a webhook only
    fires if the triggered run detects an actual material change — so `triggered=True`
    here does not guarantee an event lands; it only guarantees the check ran.

    Protected by `require_internal_caller`, matching `/internal/jobs/tighten`."""
    with session_scope() as session:
        monitor = MonitorRepo.get(session, monitor_id)
    if monitor is None:
        raise NotFound("monitor", monitor_id)
    if monitor.status != "active":
        raise HTTPException(
            status_code=409, detail=f"monitor {monitor_id} is {monitor.status}, not active"
        )

    monitor_trigger(monitor_id)
    log.info("monitor_triggered", monitor_id=monitor_id, claim_id=monitor.claim_id)
    return {"triggered": True, "monitor_id": monitor_id, "claim_id": monitor.claim_id}


def _object_name(project_id: str, *, kind: Literal["script", "cut"], filename: str) -> str:
    """Enforces PHASE_03.md §3.1's naming convention so an upload through this endpoint
    always lands somewhere `services/ingest` actually recognizes."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if kind == "script":
        if suffix != "pdf":
            raise HTTPException(422, "script uploads must be a .pdf file")
        return f"scripts/{project_id}/{filename}"

    if suffix not in _CUT_SUFFIXES:
        raise HTTPException(422, "cut uploads must be a .mp4 or .mov file")
    return f"cuts/{project_id}/{filename}"


def _generate_upload_url(bucket_name: str, object_name: str) -> str:
    return _generate_signed_url(bucket_name, object_name, method="PUT", expiration=UPLOAD_URL_TTL)


def _generate_playback_url(gcs_uri: str) -> str:
    """Signed GET URL for a `gs://...` artifact (proxy MP4/poster JPEG) so the UI can
    play/scrub it without the original, often much larger and non-public, source file
    (PHASE_06.md §6.4)."""
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"expected a gs:// URI, got {gcs_uri!r}")
    bucket_name, _, object_name = gcs_uri.removeprefix("gs://").partition("/")
    return _generate_signed_url(bucket_name, object_name, method="GET", expiration=PLAYBACK_URL_TTL)


def _generate_signed_url(
    bucket_name: str, object_name: str, *, method: Literal["PUT", "GET"], expiration: timedelta
) -> str:
    """V4 signed URL, signed via the IAM Credentials API rather than a private key file
    (Cloud Run's attached-service-account credentials carry no private key) — see
    docs/DECISIONS.md and infra/modules/iam (`roles/iam.serviceAccountTokenCreator`
    granted to sa-dashboard-api on itself)."""
    credentials, _ = google.auth.default()
    credentials.refresh(gauth_requests.Request())  # type: ignore[no-untyped-call]
    blob = storage.Client().bucket(bucket_name).blob(object_name)
    url: str = blob.generate_signed_url(
        version="v4",
        expiration=expiration,
        method=method,
        service_account_email=credentials.service_account_email,  # type: ignore[attr-defined]
        access_token=credentials.token,
    )
    return url
