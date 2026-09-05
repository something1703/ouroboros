"""services/ingest — Cloud Run, Eventarc-triggered. GCS `object.finalized` -> Gemini
document/video understanding -> Model Armor -> Claim Ledger -> Pub/Sub. PHASE_03.md §3.1, §3.5.

Eventarc delivers each event as a binary-content-mode CloudEvents HTTP POST: `ce-*`
headers carry the envelope, the body is the raw `StorageObjectData` JSON (bucket, name,
generation, ...). See docs/evidence/03-ingest.md for the verified shape.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import FastAPI, Request, Response

from packages.claims.enums import ClaimCategory
from packages.claims.models import Asset, Claim, Segment, SourceRef
from packages.common.errors import NotFound, SafetyBlocked
from packages.common.logging import get_logger
from packages.common.pubsub import publish_json
from packages.common.tracing import configure_tracing, flush_tracing, instrument_fastapi, span
from packages.gemini_client.documents import extract_script_claims
from packages.gemini_client.video import extract_cut_claims
from packages.ledger.db import session_scope
from packages.ledger.projections import Projector
from packages.ledger.repositories import AssetRepo, ClaimRepo, ProjectRepo
from packages.safety.model_armor import screen

configure_tracing(service="ingest")

app = FastAPI()
instrument_fastapi(app)
log = get_logger(__name__)

# PHASE_03.md §3.1's object naming convention. Anything else is logged and ignored (200)
# so a misplaced upload never retries forever.
_SCRIPT_RE = re.compile(r"^scripts/(?P<project_id>[^/]+)/[^/]+\.pdf$")
_CUT_RE = re.compile(r"^cuts/(?P<project_id>[^/]+)/[^/]+\.(?:mp4|mov)$")

CLAIMS_EXTRACTED_TOPIC = "claims.extracted"


@app.get("/status")
def status() -> dict[str, object]:
    return {"ok": True, "service": "ingest"}


@app.post("/")
async def handle_event(request: Request) -> Response:
    event_type = request.headers.get("ce-type", "")
    if event_type != "google.cloud.storage.object.v1.finalized":
        log.warning("ingest_ignored_event_type", event_type=event_type)
        return Response(status_code=200)

    payload: dict[str, Any] = await request.json()
    bucket = payload["bucket"]
    name = payload["name"]
    generation = str(payload["generation"])

    with span("ingest", bucket=bucket, object_name=name, generation=generation):
        try:
            _process_object(bucket=bucket, name=name, generation=generation)
        except NotFound:
            # Unknown project_id — log and ack (200): retrying won't make the project
            # exist, and Eventarc has no dead-letter path of its own to fall back to.
            log.warning("ingest_unknown_project", bucket=bucket, name=name)

    # Cloud Run freezes CPU once the response is sent (request-based billing) — flush
    # now, in-request, or BatchSpanProcessor's background export thread never runs.
    # See packages/common/tracing.flush_tracing.
    flush_tracing()
    return Response(status_code=200)


def _process_object(*, bucket: str, name: str, generation: str) -> None:
    script_match = _SCRIPT_RE.match(name)
    cut_match = _CUT_RE.match(name)
    match = script_match or cut_match
    if match is None:
        log.warning("ingest_unrecognized_object", bucket=bucket, name=name)
        return

    project_id = match.group("project_id")
    kind: Literal["script", "cut"] = "script" if script_match else "cut"
    gcs_uri = f"gs://{bucket}/{name}"
    asset_id = Asset.compute_id(bucket=bucket, name=name, generation=generation)

    with session_scope() as session:
        if AssetRepo.get(session, asset_id) is not None:
            log.info("ingest_already_processed", asset_id=asset_id, kind=kind)
            return
        project = ProjectRepo.require(session, project_id)

    claims: list[Claim]
    page_count: int | None
    duration_ms: int | None
    segments: list[Segment] = []
    proxy_uri: str | None = None
    poster_uri: str | None = None
    with span("extract", asset_id=asset_id, kind=kind):
        if kind == "script":
            script_result = extract_script_claims(gcs_uri, asset_id=asset_id, project=project)
            claims, page_count, duration_ms = script_result.claims, script_result.page_count, None
        else:
            cut_result = extract_cut_claims(gcs_uri, asset_id=asset_id, project=project)
            claims, page_count, duration_ms = cut_result.claims, None, cut_result.duration_ms
            segments = cut_result.segments
            proxy_uri, poster_uri = cut_result.proxy_uri, cut_result.poster_uri

    with span("screen", asset_id=asset_id, claim_count=len(claims)):
        screened = _screen_claims(claims)

    deduped = _dedupe(screened)
    language = deduped[0].language if deduped else None

    with span("upsert", asset_id=asset_id, claim_count=len(deduped)), session_scope() as session:
        ClaimRepo.upsert_many(session, deduped)
        AssetRepo.upsert(
            session,
            Asset(
                asset_id=asset_id,
                project_id=project_id,
                kind=kind,
                gcs_uri=gcs_uri,
                language=language,
                page_count=page_count,
                duration_ms=duration_ms,
                segments=segments,
                proxy_uri=proxy_uri,
                poster_uri=poster_uri,
                ingested_at=datetime.now(UTC),
            ),
        )
        counts_by_status = ClaimRepo.count_by_status(session, project_id)
        spend_usd = ProjectRepo.spend(session, project_id)

    with span("project", asset_id=asset_id, claim_count=len(deduped)):
        projector = Projector()
        for claim in deduped:
            projector.claim_view(
                project_id=claim.project_id,
                claim_id=claim.claim_id,
                category=claim.category.value,
                entity_text=claim.entity_text,
                claim_text=claim.claim_text,
                priority=claim.priority,
                status=claim.status.value,
                updated_at=claim.updated_at,
                risk_level=None,
                risk_score=None,
                evidence_summary=None,
                history_count=0,
                monitor_status=None,
            )
        projector.project_summary(
            project_id,
            title=project.title,
            release_date=project.release_date,
            counts_by_status=counts_by_status,
            counts_by_risk={},
            reality_drift=0.0,
            spend_usd=spend_usd,
        )

    with span("publish", asset_id=asset_id):
        publish_json(
            CLAIMS_EXTRACTED_TOPIC,
            {
                "project_id": project_id,
                "asset_id": asset_id,
                "kind": kind,
                "claim_count": len(deduped),
                "run_hint": "ingest",
            },
        )

    log.info(
        "ingest_complete",
        asset_id=asset_id,
        project_id=project_id,
        kind=kind,
        claim_count=len(deduped),
    )


def _screen_claims(claims: list[Claim]) -> list[Claim]:
    """Model Armor over every claim's source excerpt (PHASE_03.md §3.4). A hard block
    drops that one claim and continues with the rest of the asset — one adversarial
    excerpt must never sink an entire ingest run."""
    screened: list[Claim] = []
    for claim in claims:
        try:
            screen(claim.source.excerpt, context="ingest")
        except SafetyBlocked as exc:
            log.warning(
                "ingest_claim_dropped_by_safety",
                claim_id=claim.claim_id,
                reason=exc.reason,
            )
            continue
        screened.append(claim)
    return screened


def _dedupe(claims: list[Claim]) -> list[Claim]:
    """Same `normalized_text` + `category` within this asset -> one claim: keep the first
    occurrence's `source.excerpt`, and roll every other occurrence into
    `source.occurrences`/`source.all_refs` (PHASE_03.md §3.5)."""
    merged: dict[tuple[ClaimCategory, str], Claim] = {}
    for claim in claims:
        key = (claim.category, claim.normalized_text)
        existing = merged.get(key)
        if existing is None:
            merged[key] = claim
            continue
        existing.source.occurrences += 1
        existing.source.all_refs.append(_ref_dict(claim.source))
    return list(merged.values())


def _ref_dict(source: SourceRef) -> dict[str, object]:
    return {
        "page": source.page,
        "scene_number": source.scene_number,
        "scene_heading": source.scene_heading,
        "t_start_ms": source.t_start_ms,
        "t_end_ms": source.t_end_ms,
        "channel": source.channel,
        "excerpt": source.excerpt,
    }
