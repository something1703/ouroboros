from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.claims.enums import Confidence, RiskLevel, VerificationStatus
from packages.claims.models import (
    Asset,
    Citation,
    Evidence,
    FieldBasis,
    MonitorRecord,
    Risk,
    VerificationEvent,
)

_NOW = datetime(2026, 9, 3, tzinfo=UTC)


def test_asset_compute_id_is_deterministic() -> None:
    args = {
        "bucket": "ouroboros-507503-intake-dev",
        "name": "scripts/demo/x.pdf",
        "generation": "1",
    }
    assert Asset.compute_id(**args) == Asset.compute_id(**args)


def test_asset_compute_id_varies_with_generation() -> None:
    """The whole point of keying on generation (PHASE_03.md §3.1, docs/DECISIONS.md): a
    redelivery of the *same* object.finalized event must collide (same asset_id, so
    services/ingest's idempotency check skips it), but a genuinely new upload to the
    same path (a new generation) must not be mistaken for the old one."""
    same_generation = Asset.compute_id(bucket="b", name="scripts/demo/x.pdf", generation="1")
    redelivered = Asset.compute_id(bucket="b", name="scripts/demo/x.pdf", generation="1")
    new_upload = Asset.compute_id(bucket="b", name="scripts/demo/x.pdf", generation="2")

    assert same_generation == redelivered
    assert same_generation != new_upload


def test_citation_requires_url() -> None:
    citation = Citation(url="https://example.com", retrieved_at=_NOW)
    assert citation.excerpt is None


def test_field_basis_holds_citations() -> None:
    basis = FieldBasis(
        field="composition_rights_holder",
        citations=[Citation(url="https://example.com", retrieved_at=_NOW)],
        reasoning="Found on the publisher's official site.",
        confidence=Confidence.HIGH,
    )
    assert len(basis.citations) == 1


def test_evidence_defaults_evidence_id_and_cost() -> None:
    evidence = Evidence(
        claim_id="c1",
        cycle=1,
        method="task",
        output={"work_title": "Song"},
        basis=[],
        overall_confidence=Confidence.MEDIUM,
        created_at=_NOW,
    )
    assert len(evidence.evidence_id) == 26  # ULID
    assert evidence.cost_usd == 0


def test_evidence_cycle_must_be_at_least_one() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            claim_id="c1",
            cycle=0,
            method="task",
            output={},
            basis=[],
            overall_confidence=Confidence.UNKNOWN,
            created_at=_NOW,
        )


def test_risk_score_must_be_in_unit_interval() -> None:
    with pytest.raises(ValidationError):
        Risk(
            claim_id="c1",
            evidence_id="e1",
            level=RiskLevel.LOW,
            score=1.5,
            rationale="x",
            assessed_at=_NOW,
        )


def test_risk_defaults() -> None:
    risk = Risk(
        claim_id="c1",
        evidence_id="e1",
        level=RiskLevel.LOW,
        score=0.2,
        rationale="x",
        assessed_at=_NOW,
    )
    assert risk.remediation_suggested is False
    assert risk.remediation_kind == "none"
    assert risk.territory_flags == {}


def test_verification_event_tracks_status_transition() -> None:
    event = VerificationEvent(
        claim_id="c1",
        at=_NOW,
        actor="agent",
        from_status=VerificationStatus.TRIAGED,
        to_status=VerificationStatus.VERIFIED,
        note="verified via task run",
    )
    assert event.from_status == VerificationStatus.TRIAGED
    assert event.to_status == VerificationStatus.VERIFIED
    assert len(event.event_id) == 26


def test_monitor_record_requires_frequency() -> None:
    monitor = MonitorRecord(
        monitor_id="mon_1",
        claim_id="c1",
        type="snapshot",
        task_run_id="trun_1",
        frequency="1w",
        status="active",
        created_at=_NOW,
    )
    assert monitor.status == "active"
    assert monitor.last_event_at is None
