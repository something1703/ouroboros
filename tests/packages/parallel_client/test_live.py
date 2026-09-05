"""Live verification against the real Parallel API — one smoke test per wrapper module,
codifying the manual checks run during Phase 4 development (docs/evidence/04-verify.txt).
Never run in CI (`-m live`, excluded by `make test`) — needs a real PARALLEL_API_KEY and
costs real (small) money. Run with `make test-live`.
"""

from __future__ import annotations

import pytest

from packages.claims.enums import ClaimCategory, Confidence
from packages.parallel_client.entity import search as entity_search
from packages.parallel_client.extract import extract
from packages.parallel_client.memory import retrieve as memory_retrieve
from packages.parallel_client.monitor import cancel, create_snapshot, events
from packages.parallel_client.responses import ask
from packages.parallel_client.search import build_objective, search
from packages.parallel_client.task import build_input, run

pytestmark = pytest.mark.live


def test_search_returns_real_hits_with_screened_excerpts() -> None:
    objective, queries = build_objective(ClaimCategory.MUSIC, "Bohemian Rhapsody", ["us", "gb"])
    result = search(objective, queries, mode="fast", category=ClaimCategory.MUSIC, location="us")
    assert result.hits
    assert all(hit.url.startswith("http") for hit in result.hits)


def test_task_run_returns_parsed_basis_with_confidence() -> None:
    task_input = build_input(
        "A Coca-Cola can is visible on the table in Sc. 12",
        jurisdictions=["us"],
        excerpt="pours coffee into a Coca-Cola can",
        top_urls=[],
    )
    result = run(task_input, "legal_brand", claim_id="live-test-brand", project_id="demo")
    assert result.run_id.startswith("trun_")
    assert result.overall_confidence in {Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW}
    assert result.basis
    assert isinstance(result.content, dict)
    assert "brand_owner" in result.content


def test_extract_returns_screened_excerpts() -> None:
    hits = extract(
        ["https://en.wikipedia.org/wiki/Coca-Cola"],
        objective="Who owns the Coca-Cola trademark?",
    )
    assert hits
    assert hits[0].excerpts


def test_entity_search_returns_hits() -> None:
    hits = entity_search(
        "performing rights organizations in the United States", "companies", limit=5
    )
    assert hits
    assert all(hit.url for hit in hits)


def test_responses_ask_returns_structured_answer_with_citations() -> None:
    result = ask(
        "Is the song Bohemian Rhapsody by Queen in the public domain in the US?",
        effort="low",
    )
    assert result.answer["verdict"] in {
        "supported",
        "contradicted",
        "partially_supported",
        "unverifiable",
    }
    assert result.citations


def test_monitor_snapshot_lifecycle() -> None:
    task_input = build_input(
        "A Coca-Cola can is visible on the table",
        jurisdictions=["us"],
        excerpt="a can on the table",
        top_urls=[],
    )
    task_result = run(task_input, "legal_brand", claim_id="live-test-monitor", project_id="demo")

    monitor = create_snapshot(
        task_result.run_id,
        frequency="1w",
        webhook_url="https://dashboard-api-492372502792.us-central1.run.app/webhooks/parallel/monitor",
        claim_id="live-test-monitor",
        project_id="demo",
    )
    try:
        assert monitor.status == "active"
        assert monitor.type == "snapshot"
        events(monitor.monitor_id)  # does not raise
    finally:
        cancel(monitor.monitor_id)


def test_memory_retrieve_does_not_raise() -> None:
    # Graceful either way: real hits if memory has prior runs for this scope, empty
    # list if not — the point is the call succeeds against the real endpoint.
    hits = memory_retrieve("Coca-Cola", "studio-demo", limit=5)
    assert isinstance(hits, list)
