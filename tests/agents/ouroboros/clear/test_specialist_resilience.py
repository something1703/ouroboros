"""PHASE_09.md §9.5: two real resilience properties of `verify_batch`
(agents/ouroboros/clear/specialist.py) -- a Parallel failure on one claim in a batch
is isolated (the claim ends up `status="error"`, the rest of the batch still
completes), and a budget cap hit mid-batch stops that one claim gracefully
(`status="pending"`, a `"budget exceeded"` note) rather than crashing or silently
continuing to spend. Exercised against the real `verify_batch` algorithm with every
Parallel/ledger call mocked (no network, no DB) -- specialist.py's own module-level
imports are patched directly, the same names it calls internally.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import pytest

from agents.ouroboros.clear import specialist
from packages.claims.enums import Confidence
from packages.common.errors import BudgetExceeded, ParallelError
from packages.parallel_client.search import SearchResult
from packages.parallel_client.task import TaskResult

_CLAIMS = {
    "fail-1": {
        "category": "music",
        "entity_text": "Some Song",
        "claim_text": "A record player spins Some Song.",
        "priority": 3,
        "source": {"excerpt": "A record player spins Some Song."},
    },
    "ok-1": {
        "category": "music",
        "entity_text": "Other Song",
        "claim_text": "A radio plays Other Song.",
        "priority": 3,
        "source": {"excerpt": "A radio plays Other Song."},
    },
    "over-budget-1": {
        "category": "music",
        "entity_text": "Expensive Song",
        "claim_text": "A jukebox plays Expensive Song.",
        "priority": 3,
        "source": {"excerpt": "A jukebox plays Expensive Song."},
    },
}


class _Tracked:
    def __init__(self) -> None:
        self.evidence: list[str] = []
        self.status: list[tuple[str, str, str]] = []


@pytest.fixture
def tracked(monkeypatch: pytest.MonkeyPatch) -> _Tracked:
    tracked = _Tracked()

    monkeypatch.setattr(
        specialist.ledger, "get_claim", lambda claim_id: json.dumps(_CLAIMS[claim_id])
    )

    def _check_budget(project_id: str) -> None:
        pass  # the pre-flight per-project check; over-budget is enforced per-claim below

    monkeypatch.setattr(specialist, "check_budget", _check_budget)

    def _check_and_record_cost(project_id: str, claim_id: str, *, api: str, sku: str) -> Decimal:
        if claim_id == "over-budget-1":
            raise BudgetExceeded(project_id, 9.999, 10.0)
        return Decimal("0.001")

    monkeypatch.setattr(specialist, "check_and_record_cost", _check_and_record_cost)
    monkeypatch.setattr(specialist, "build_objective", lambda category, entity, j: ("obj", ["q"]))
    monkeypatch.setattr(
        specialist,
        "search",
        lambda *a, **kw: SearchResult(hits=[], search_id="search_test", session_id="sess_test"),
    )
    monkeypatch.setattr(specialist, "toolbox_mcp_servers", lambda: None)
    monkeypatch.setattr(specialist, "should_escalate", lambda confidence, priority: False)

    def _run_task(
        task_input: str,
        spec_name: str,
        *,
        claim_id: str,
        project_id: str,
        processor: str,
        mcp_servers: object,
        memory_scope_key: str,
    ) -> TaskResult:
        if claim_id == "fail-1":
            raise ParallelError("Parallel returned 500 after retries")
        return TaskResult(
            run_id="trun_test",
            content={"composition_rights_holder": "Test Publisher"},
            basis=[],
            overall_confidence=Confidence.HIGH,
            processor="core-fast",
        )

    monkeypatch.setattr(specialist, "run_task", _run_task)
    monkeypatch.setattr(
        specialist, "write_evidence", lambda claim_id, **kw: tracked.evidence.append(claim_id)
    )
    monkeypatch.setattr(
        specialist,
        "set_status",
        lambda claim_id, status, *, note="": tracked.status.append((claim_id, status, note)),
    )
    return tracked


def test_one_claims_parallel_failure_is_isolated_from_the_rest_of_the_batch(
    tracked: _Tracked,
) -> None:
    result = asyncio.run(
        specialist.verify_batch(
            ["fail-1", "ok-1"],
            spec_name="legal_music",
            project_id="demo",
            studio_id="studio-1",
            jurisdictions=["us"],
        )
    )

    assert result["verified"] == ["ok-1"]
    assert result["escalated"] == []
    assert len(result["errors"]) == 1
    assert result["errors"][0]["claim_id"] == "fail-1"
    assert "500" in result["errors"][0]["error"]
    assert ("fail-1", "error") in {(c, s) for c, s, _n in tracked.status}
    assert tracked.evidence == ["ok-1"]  # no evidence written for the failed claim


def test_budget_exceeded_mid_batch_stops_that_claim_gracefully(tracked: _Tracked) -> None:
    result = asyncio.run(
        specialist.verify_batch(
            ["ok-1", "over-budget-1"],
            spec_name="legal_music",
            project_id="demo",
            studio_id="studio-1",
            jurisdictions=["us"],
        )
    )

    assert result["verified"] == ["ok-1"]
    assert result["escalated"] == []
    assert len(result["errors"]) == 1
    assert result["errors"][0]["claim_id"] == "over-budget-1"
    assert "budget_exceeded" in result["errors"][0]["error"]
    # the over-budget claim is set back to "pending" (retryable later), not "error"
    assert ("over-budget-1", "pending", "budget exceeded") in tracked.status
    assert tracked.evidence == ["ok-1"]
