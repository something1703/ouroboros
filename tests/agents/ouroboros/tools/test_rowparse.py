"""Parsing of a `get_claim` flat JSON row into domain Claim/Evidence objects."""

from __future__ import annotations

from agents.ouroboros.tools.rowparse import claim_from_row, evidence_from_row

_CLAIM_ROW: dict[str, object] = {
    "claim_id": "c1",
    "project_id": "demo",
    "studio_id": "studio-demo",
    "kind": "legal",
    "category": "brand",
    "entity_text": "Coca-Cola",
    "normalized_text": "coca cola",
    "claim_text": "A Coca-Cola can is on the table.",
    "language": "en",
    "source": {"asset_id": "a1", "page": 1, "excerpt": "a can on the table"},
    "jurisdictions": ["us", "gb"],
    "priority": 1,
    "status": "verified",
    "created_at": "2026-09-04T00:00:00+00:00",
    "updated_at": "2026-09-04T00:00:00+00:00",
    "evidence_id": "e1",
    "cycle": 1,
    "method": "task",
    "parallel_run_id": "trun_abc",
    "evidence_output": {"brand_owner": "The Coca-Cola Company"},
    "evidence_basis": [
        {
            "field": "brand_owner",
            "citations": [
                {"url": "https://example.com", "retrieved_at": "2026-09-04T00:00:00+00:00"}
            ],
            "reasoning": "because",
            "confidence": "high",
        }
    ],
    "overall_confidence": "high",
    "evidence_created_at": "2026-09-04T00:00:00+00:00",
}


def test_claim_from_row_round_trips_fields() -> None:
    claim = claim_from_row(_CLAIM_ROW)
    assert claim.claim_id == "c1"
    assert claim.entity_text == "Coca-Cola"
    assert claim.category.value == "brand"
    assert claim.jurisdictions == ["us", "gb"]
    assert claim.priority == 1


def test_evidence_from_row_round_trips_fields() -> None:
    evidence = evidence_from_row(_CLAIM_ROW, claim_id="c1")
    assert evidence is not None
    assert evidence.evidence_id == "e1"
    assert evidence.parallel_run_id == "trun_abc"
    assert evidence.overall_confidence.value == "high"
    assert evidence.output == {"brand_owner": "The Coca-Cola Company"}
    assert len(evidence.basis) == 1
    assert evidence.basis[0].citations[0].url == "https://example.com"


def test_evidence_from_row_returns_none_when_no_evidence_yet() -> None:
    row = {**_CLAIM_ROW, "evidence_id": None}
    assert evidence_from_row(row, claim_id="c1") is None


def test_evidence_from_row_handles_missing_parallel_run_id() -> None:
    row = {**_CLAIM_ROW, "parallel_run_id": None, "method": "search"}
    evidence = evidence_from_row(row, claim_id="c1")
    assert evidence is not None
    assert evidence.parallel_run_id is None
