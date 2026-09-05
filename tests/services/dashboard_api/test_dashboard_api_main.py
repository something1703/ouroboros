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
from packages.claims.enums import ClaimCategory, ClaimKind, Confidence
from packages.claims.models import Claim, Evidence, Project, Risk, RiskLevel, SourceRef
from packages.ledger.repositories import ClaimRepo, EvidenceRepo, ProjectRepo, RiskRepo
from services.dashboard_api.auth import UserContext, get_current_user, require_internal_caller

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


@pytest.fixture(autouse=True)
def _stub_projector(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No real Firestore in the offline test env -- the new endpoints (claim override,
    events, metrics) all write/read through `_projector`, which every other test in
    this file never touched (the pre-Phase-8 endpoints don't call it)."""
    monkeypatch.setattr(dashboard_api._projector, "claim_view", lambda **_kwargs: None)
    monkeypatch.setattr(dashboard_api._projector, "get_project_summary", lambda _project_id: None)
    monkeypatch.setattr(dashboard_api._projector, "list_events", lambda _project_id, **_kwargs: [])
    yield


def _as(email: str, role: str) -> None:
    dashboard_api.app.dependency_overrides[get_current_user] = lambda: UserContext(
        email=email, role=role
    )


def _as_internal_caller() -> None:
    dashboard_api.app.dependency_overrides[require_internal_caller] = lambda: None


@pytest.fixture(autouse=True)
def _clear_auth_override() -> Iterator[None]:
    yield
    dashboard_api.app.dependency_overrides.pop(get_current_user, None)
    dashboard_api.app.dependency_overrides.pop(require_internal_caller, None)


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


def test_status(client: TestClient) -> None:
    response = client.get("/status")
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


def test_list_projects_requires_auth(client: TestClient) -> None:
    assert client.get("/projects").status_code == 422  # missing Authorization header


def test_list_and_get_project(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    _as("iamrudra1703@gmail.com", "producer")

    listed = client.get("/projects")
    assert listed.status_code == 200
    assert [p["project_id"] for p in listed.json()] == ["demo"]

    got = client.get("/projects/demo")
    assert got.status_code == 200
    assert got.json()["title"] == "Demo Film"


def test_create_project(client: TestClient) -> None:
    _as("iamrudra1703@gmail.com", "producer")
    response = client.post(
        "/projects",
        json={"project_id": "new-film", "studio_id": "studio-1", "title": "New Film"},
    )
    assert response.status_code == 201
    assert response.json()["project_id"] == "new-film"


def test_create_project_conflict_on_duplicate(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    _as("iamrudra1703@gmail.com", "producer")
    response = client.post(
        "/projects", json={"project_id": "demo", "studio_id": "studio-1", "title": "Demo Film"}
    )
    assert response.status_code == 409


def test_get_claim_detail(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    claim = _seed_claim(db_session)
    _as("iamrudra1703@gmail.com", "producer")

    response = client.get(f"/projects/demo/claims/{claim.claim_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["claim"]["claim_id"] == claim.claim_id
    assert body["evidence_history"] == []
    assert body["risk"] is None
    assert body["history"] == []


def test_override_claim_status_as_legal(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    claim = _seed_claim(db_session)  # kind=legal, category=brand
    _as("rvsrathore17@gmail.com", "legal")

    response = client.patch(
        f"/projects/demo/claims/{claim.claim_id}",
        json={"status": "verified", "note": "cleared manually, license confirmed"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["claim"]["status"] == "verified"
    assert len(body["history"]) == 1
    assert body["history"][0]["actor"] == "human"


def test_override_claim_wrong_role_403s(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    claim = _seed_claim(db_session)  # kind=legal
    _as("ujjwaltyagi9605@gmail.com", "editorial")  # editorial overrides factual, not legal

    response = client.patch(
        f"/projects/demo/claims/{claim.claim_id}",
        json={"status": "verified", "note": "attempted override"},
    )
    assert response.status_code == 403


def test_override_claim_producer_always_403s(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    claim = _seed_claim(db_session)
    _as("iamrudra1703@gmail.com", "producer")

    response = client.patch(
        f"/projects/demo/claims/{claim.claim_id}",
        json={"status": "verified", "note": "attempted override"},
    )
    assert response.status_code == 403


def test_override_risk_without_existing_risk_409s(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    claim = _seed_claim(db_session)
    _as("rvsrathore17@gmail.com", "legal")

    response = client.patch(
        f"/projects/demo/claims/{claim.claim_id}",
        json={"risk_level": "low", "note": "no evidence yet"},
    )
    assert response.status_code == 409


def test_override_risk_with_existing_risk(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    claim = _seed_claim(db_session)
    evidence = Evidence(
        claim_id=claim.claim_id,
        cycle=1,
        method="search",
        output={},
        basis=[],
        overall_confidence=Confidence.HIGH,
        created_at=datetime.now(UTC),
    )
    EvidenceRepo.insert(db_session, evidence)
    RiskRepo.upsert(
        db_session,
        Risk(
            claim_id=claim.claim_id,
            evidence_id=evidence.evidence_id,
            level=RiskLevel.HIGH,
            score=0.8,
            rationale="initial assessment",
            assessed_at=datetime.now(UTC),
        ),
    )
    db_session.commit()
    _as("rvsrathore17@gmail.com", "legal")

    response = client.patch(
        f"/projects/demo/claims/{claim.claim_id}",
        json={"risk_level": "low", "note": "reviewed, license confirmed clear"},
    )
    assert response.status_code == 200
    assert response.json()["risk"]["level"] == "low"


def test_events_feed(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    _as("iamrudra1703@gmail.com", "producer")
    response = client.get("/projects/demo/events")
    assert response.status_code == 200
    assert response.json() == {"events": [], "next_before": None}


def test_metrics(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    _as("iamrudra1703@gmail.com", "producer")
    response = client.get("/projects/demo/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["counts_by_status"] == {}
    assert body["current_cadence"] in {"1h", "1d", "1w"}


def test_internal_endpoint_requires_authorization_header(client: TestClient) -> None:
    response = client.post("/internal/jobs/tighten")
    assert response.status_code == 422  # missing Authorization header entirely


def test_internal_endpoint_works_for_an_authorized_internal_caller(client: TestClient) -> None:
    _as_internal_caller()
    response = client.post("/internal/jobs/tighten")
    assert response.status_code == 200
    assert response.json() == {"total": 0, "updated": 0, "unchanged": 0, "errors": []}


def test_get_me_returns_the_signed_in_user(client: TestClient) -> None:
    _as("rvsrathore17@gmail.com", "legal")
    response = client.get("/me")
    assert response.status_code == 200
    assert response.json() == {"email": "rvsrathore17@gmail.com", "role": "legal"}


def test_get_me_requires_auth(client: TestClient) -> None:
    assert client.get("/me").status_code == 422  # missing Authorization header


def test_trigger_all_monitors_with_none_active(client: TestClient, db_session: Session) -> None:
    _seed_project(db_session)
    _as("iamrudra1703@gmail.com", "producer")
    response = client.post("/projects/demo/monitors/trigger-all")
    assert response.status_code == 200
    assert response.json() == {"total": 0, "triggered": 0, "errors": []}
