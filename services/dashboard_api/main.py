"""services/dashboard_api — Cloud Run, FastAPI. Thin ingest-facing slice for Phase 3
(PHASE_03.md §3.6): signed-URL asset upload, asset listing, claim listing. The demo may
upload via `gsutil` directly; the browser upload flow is Phase 8. Broader dashboard
endpoints (evidence, runs, exports, Ask Ouroboros) land in later phases per
services/dashboard_api/README.md.
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Literal

import google.auth
import google.auth.transport.requests as gauth_requests
import google.cloud.storage as storage
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from packages.claims.enums import ClaimCategory, VerificationStatus
from packages.claims.models import Asset, Claim
from packages.common.errors import NotFound
from packages.common.tracing import configure_tracing, instrument_fastapi
from packages.ledger.db import session_scope
from packages.ledger.repositories import AssetRepo, ClaimRepo, ProjectRepo

configure_tracing(service="dashboard_api")

app = FastAPI(title="Ouroboros Dashboard API")
instrument_fastapi(app)

UPLOAD_URL_TTL = timedelta(minutes=15)
_CUT_SUFFIXES = {"mp4", "mov"}


class UploadRequest(BaseModel):
    kind: Literal["script", "cut"]
    filename: str


class UploadResponse(BaseModel):
    upload_url: str
    gcs_uri: str


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
    """V4 signed PUT URL, signed via the IAM Credentials API rather than a private key
    file (Cloud Run's attached-service-account credentials carry no private key) — see
    docs/DECISIONS.md and infra/modules/iam (`roles/iam.serviceAccountTokenCreator`
    granted to sa-dashboard-api on itself)."""
    credentials, _ = google.auth.default()
    credentials.refresh(gauth_requests.Request())  # type: ignore[no-untyped-call]
    blob = storage.Client().bucket(bucket_name).blob(object_name)
    url: str = blob.generate_signed_url(
        version="v4",
        expiration=UPLOAD_URL_TTL,
        method="PUT",
        service_account_email=credentials.service_account_email,  # type: ignore[attr-defined]
        access_token=credentials.token,
    )
    return url
