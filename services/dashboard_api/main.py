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
from datetime import timedelta
from typing import Literal

import google.auth
import google.auth.transport.requests as gauth_requests
import google.cloud.storage as storage
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from packages.claims.enums import ClaimCategory, VerificationStatus
from packages.claims.models import Asset, Claim, Segment
from packages.common.errors import NotFound
from packages.common.logging import get_logger
from packages.common.tracing import configure_tracing, instrument_fastapi
from packages.ledger.db import session_scope
from packages.ledger.repositories import AssetRepo, ClaimRepo, EvidenceRepo, ProjectRepo, RiskRepo

from .runs import start_run

configure_tracing(service="dashboard_api")
log = get_logger(__name__)

app = FastAPI(title="Ouroboros Dashboard API")
instrument_fastapi(app)

UPLOAD_URL_TTL = timedelta(minutes=15)
PLAYBACK_URL_TTL = timedelta(hours=1)
_CUT_SUFFIXES = {"mp4", "mov"}


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


@app.exception_handler(NotFound)
def _not_found_handler(_request: Request, exc: NotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {"ok": True, "service": "dashboard_api"}


@app.post("/projects/{project_id}/assets", response_model=UploadResponse)
def create_upload_url(project_id: str, body: UploadRequest) -> UploadResponse:
    with session_scope() as session:
        ProjectRepo.require(session, project_id)

    object_name = _object_name(project_id, kind=body.kind, filename=body.filename)
    bucket = os.environ["INTAKE_BUCKET"]
    upload_url = _generate_upload_url(bucket, object_name)
    return UploadResponse(upload_url=upload_url, gcs_uri=f"gs://{bucket}/{object_name}")


@app.get("/projects/{project_id}/assets", response_model=list[Asset])
def list_assets(project_id: str) -> list[Asset]:
    with session_scope() as session:
        ProjectRepo.require(session, project_id)
        return AssetRepo.list_by_project(session, project_id)


@app.get("/projects/{project_id}/claims", response_model=list[Claim])
def list_claims(
    project_id: str,
    status: VerificationStatus | None = Query(default=None),
    category: ClaimCategory | None = Query(default=None),
) -> list[Claim]:
    with session_scope() as session:
        ProjectRepo.require(session, project_id)
        return ClaimRepo.list_by_project(
            session, project_id, status=status, category=category.value if category else None
        )


@app.get("/assets/{asset_id}/timeline", response_model=TimelineResponse)
def get_asset_timeline(asset_id: str) -> TimelineResponse:
    """PHASE_06.md §6.4: segments + every claim sourced from this asset, each with its
    latest verdict/risk/top citation so the UI can plot a scrubber without a second
    round trip per claim."""
    with session_scope() as session:
        asset = AssetRepo.get(session, asset_id)
        if asset is None:
            raise NotFound("asset", asset_id)
        claims = ClaimRepo.list_by_asset(session, asset_id)
        timeline_claims = [_timeline_claim(session, claim) for claim in claims]
    timeline_claims.sort(key=lambda c: (c.t_start_ms is None, c.t_start_ms or 0))
    return TimelineResponse(
        asset_id=asset.asset_id,
        duration_ms=asset.duration_ms,
        segments=asset.segments,
        claims=timeline_claims,
    )


@app.get("/assets/{asset_id}/segments", response_model=SegmentsResponse)
def get_asset_segments(asset_id: str) -> SegmentsResponse:
    with session_scope() as session:
        asset = AssetRepo.get(session, asset_id)
        if asset is None:
            raise NotFound("asset", asset_id)
        return SegmentsResponse(asset_id=asset.asset_id, segments=asset.segments)


@app.get("/assets/{asset_id}/proxy", response_model=PlaybackResponse)
def get_asset_proxy(asset_id: str) -> PlaybackResponse:
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
        t_start_ms=claim.source.t_start_ms,
        t_end_ms=claim.source.t_end_ms,
        channel=claim.source.channel,
        status=claim.status.value,
        verdict=verdict,
        risk_level=risk.level.value if risk else None,
        top_citation=top_citation,
    )


@app.post("/projects/{project_id}/runs", response_model=StartRunResponse)
async def create_run(project_id: str, body: StartRunRequest) -> StartRunResponse:
    # Must be `async def`, not a plain sync handler -- found live: a sync FastAPI route
    # runs in Starlette's worker threadpool, not on the event loop thread, so
    # `start_run`'s internal `asyncio.create_task` had no running loop to attach to
    # ("RuntimeError: no running event loop"). An async handler runs directly on the
    # event loop, where create_task works as intended.
    with session_scope() as session:
        ProjectRepo.require(session, project_id)
    run_id = start_run(project_id, body.asset_id, mode=body.mode)
    return StartRunResponse(run_id=run_id)


@app.post("/internal/runs/auto")
async def auto_run(request: Request) -> dict[str, object]:
    """Pub/Sub push target on `claims.extracted` (infra/modules/pubsub — the
    subscription itself is added alongside this endpoint). Starts a CLEAR run
    automatically after ingest, only when `AUTO_RUN_AFTER_INGEST=true`; otherwise a
    no-op 200 (never a Pub/Sub-retry-triggering error) so the feature can be toggled
    without touching the subscription."""
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
