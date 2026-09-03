"""Contract tests for services/dashboard_api (PHASE_03.md §3.6). Runs against the real
local Postgres (tests/conftest.py's `engine`/`db_session` fixtures) — the same repository
layer the service itself uses — with only the outbound GCS-signing call mocked, since
that needs real IAM credentials `make test` doesn't have.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import services.dashboard_api.main as dashboard_api
from packages.claims.enums import ClaimCategory, ClaimKind
from packages.claims.models import Claim, Project, SourceRef
from packages.ledger.repositories import ClaimRepo, ProjectRepo

pytestmark = pytest.mark.usefixtures("engine")


@pytest.fixture(autouse=True)
def _stub_signing(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("INTAKE_BUCKET", "test-intake-bucket")
    monkeypatch.setattr(
        dashboard_api,
        "_generate_upload_url",
        lambda bucket, name: f"https://storage.googleapis.com/{bucket}/{name}?signed=1",
    )
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(dashboard_api.app)


def _seed_project(db_session: Session, project_id: str = "demo") -> None:
    ProjectRepo.upsert(
        db_session,
        Project(
            project_id=project_id,
            studio_id="studio-1",
            title="Demo Film",
            created_at=datetime.now(UTC),
        ),
    )
    db_session.commit()


def _seed_claim(db_session: Session, project_id: str = "demo") -> Claim:
    source = SourceRef(asset_id="asset-1", page=12, excerpt="A Coca-Cola can is on the table.")
    claim = Claim.new(
        project_id=project_id,
        studio_id="studio-1",
        kind=ClaimKind.LEGAL,
        category=ClaimCategory.BRAND,
        entity_text="Coca-Cola",
        claim_text="A Coca-Cola can is visible on the table in Sc. 12",
        language="en",
        source=source,
        jurisdictions=["us"],
    )
    ClaimRepo.upsert(db_session, claim)
    db_session.commit()
    return claim


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "service": "dashboard_api"}


def test_create_upload_url_for_script(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    response = client.post(
        "/projects/demo/assets", json={"kind": "script", "filename": "final_draft.pdf"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["gcs_uri"] == "gs://test-intake-bucket/scripts/demo/final_draft.pdf"
    assert body["upload_url"].startswith("https://storage.googleapis.com/")


def test_create_upload_url_for_cut(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    response = client.post("/projects/demo/assets", json={"kind": "cut", "filename": "reel.mp4"})
    assert response.status_code == 200
    assert response.json()["gcs_uri"] == "gs://test-intake-bucket/cuts/demo/reel.mp4"


def test_create_upload_url_rejects_wrong_extension(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    response = client.post("/projects/demo/assets", json={"kind": "script", "filename": "reel.mp4"})
    assert response.status_code == 422


def test_create_upload_url_unknown_project_404s(client: TestClient) -> None:
    response = client.post(
        "/projects/does-not-exist/assets", json={"kind": "script", "filename": "x.pdf"}
    )
    assert response.status_code == 404


def test_list_assets_unknown_project_404s(client: TestClient) -> None:
    response = client.get("/projects/does-not-exist/assets")
    assert response.status_code == 404


def test_list_claims_returns_seeded_claim(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    claim = _seed_claim(db_session)

    response = client.get("/projects/demo/claims")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["claim_id"] == claim.claim_id
    assert body[0]["entity_text"] == "Coca-Cola"


def test_list_claims_filters_by_category(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    _seed_claim(db_session)

    matching = client.get("/projects/demo/claims", params={"category": "brand"})
    assert len(matching.json()) == 1

    non_matching = client.get("/projects/demo/claims", params={"category": "music"})
    assert non_matching.json() == []


def test_openapi_schema_renders(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/projects/{project_id}/assets" in schema["paths"]
    assert "/projects/{project_id}/claims" in schema["paths"]
