"""Parallel tools (ADK_AGENTS.md §0) — thin ADK-compatible wrappers around
packages/parallel_client/*. Each function takes only JSON-schema-friendly parameters
(ADK infers the tool's function-calling schema from type hints + this docstring) and
returns a plain JSON-serializable dict, since packages/parallel_client's own return
types are Pydantic models/dataclasses the model can't read directly.
"""

from __future__ import annotations

from datetime import date

from config.parallel import RESPONSES_EFFORT_DEFAULT, SEARCH_MODE_DEFAULT, TASK_PROCESSOR_DEFAULT
from packages.claims.enums import ClaimCategory
from packages.parallel_client import entity as entity_client
from packages.parallel_client import extract as extract_client
from packages.parallel_client import memory as memory_client
from packages.parallel_client import monitor as monitor_client
from packages.parallel_client import responses as responses_client
from packages.parallel_client import search as search_client
from packages.parallel_client import task as task_client
from packages.parallel_client.task import RunHandle, TaskResult

from .mcp import toolbox_mcp_servers
from .resilience import resilient as _resilient


@_resilient
def search(
    objective: str,
    queries: list[str],
    *,
    category: str,
    location: str | None = None,
    exclude_domains: list[str] | None = None,
    after_date_iso: str | None = None,
    mode: str = SEARCH_MODE_DEFAULT,
    claim_id: str | None = None,
) -> dict[str, object]:
    """Search the live web via Parallel. `category` (a ClaimCategory value) steers the
    default exclude_domains for legal categories. `after_date_iso` is an optional
    'YYYY-MM-DD' string."""
    after = date.fromisoformat(after_date_iso) if after_date_iso else None
    result = search_client.search(
        objective,
        queries,
        mode=mode,  # type: ignore[arg-type]
        location=location,
        exclude_domains=exclude_domains,
        after_date=after,
        category=ClaimCategory(category),
        claim_id=claim_id,
    )
    return {
        "search_id": result.search_id,
        "session_id": result.session_id,
        "hits": [hit.model_dump(mode="json") for hit in result.hits],
    }


@_resilient
def task_run(
    task_input: str,
    spec_name: str,
    *,
    claim_id: str,
    project_id: str,
    studio_id: str,
    processor: str = TASK_PROCESSOR_DEFAULT,
    cycle: int = 1,
    previous_interaction_id: str | None = None,
    wait: bool = True,
) -> dict[str, object]:
    """Run a Parallel Task against one of the JSON output specs in
    packages/parallel_client/specs/ (e.g. 'legal_music', 'factual_claim'). Attaches our
    read-only Toolbox MCP server so Parallel can look up prior decisions. `wait=False`
    returns a run_id immediately; completion then arrives via webhook."""
    result = task_client.run(
        task_input,
        spec_name,
        claim_id=claim_id,
        project_id=project_id,
        cycle=cycle,
        processor=processor,
        mcp_servers=toolbox_mcp_servers(),
        previous_interaction_id=previous_interaction_id,
        memory_scope_key=studio_id,
        wait=wait,
    )
    if isinstance(result, RunHandle):
        return {"run_id": result.run_id, "status": "pending"}
    assert isinstance(result, TaskResult)
    return {
        "run_id": result.run_id,
        "content": result.content,
        "basis": [b.model_dump(mode="json") for b in result.basis],
        "overall_confidence": result.overall_confidence.value,
        "processor": result.processor,
    }


@_resilient
def responses(
    question: str, *, schema_name: str = "factual_quick", effort: str = RESPONSES_EFFORT_DEFAULT
) -> dict[str, object]:
    """Ask Parallel's Responses API a question, grounded in live web research, returning
    a structured answer conforming to `schema_name` plus citations."""
    result = responses_client.ask(question, schema=schema_name, effort=effort)  # type: ignore[arg-type]
    return {
        "answer": result.answer,
        "citations": [c.model_dump(mode="json") for c in result.citations],
    }


@_resilient
def entity_search(objective: str, entity_type: str, *, limit: int = 25) -> dict[str, object]:
    """Resolve real-world entities (publishers, labels, estates, agents) via Parallel's
    Entity Search. `entity_type` is 'people' or 'companies'."""
    hits = entity_client.search(objective, entity_type, limit=limit)  # type: ignore[arg-type]
    return {"hits": [h.model_dump(mode="json") for h in hits]}


@_resilient
def extract(urls: list[str], *, objective: str, full_content: bool = False) -> dict[str, object]:
    """Pull markdown + excerpts from up to 5 URLs (licensing pages, permit pages,
    trademark records) via Parallel Extract."""
    hits = extract_client.extract(urls, objective=objective, full_content=full_content)
    return {"hits": [h.model_dump(mode="json") for h in hits]}


@_resilient
def monitor_create_snapshot(
    task_run_id: str,
    *,
    frequency: str,
    webhook_url: str,
    claim_id: str,
    project_id: str,
    studio_id: str,
) -> dict[str, object]:
    """Watch a completed Task run for changes (snapshot Monitor) — used for high/blocking
    risk claims."""
    record = monitor_client.create_snapshot(
        task_run_id,
        frequency=frequency,  # type: ignore[arg-type]
        webhook_url=webhook_url,
        claim_id=claim_id,
        project_id=project_id,
        memory_scope_key=studio_id,
    )
    return record.model_dump(mode="json")


@_resilient
def monitor_create_stream(
    query: str,
    *,
    frequency: str,
    webhook_url: str,
    claim_id: str,
    project_id: str,
    studio_id: str,
    location: str | None = None,
) -> dict[str, object]:
    """Watch the live web for new developments matching `query` (event_stream Monitor) —
    used for litigious brands/persons or developing factual stories."""
    record = monitor_client.create_stream(
        query,
        frequency=frequency,  # type: ignore[arg-type]
        webhook_url=webhook_url,
        claim_id=claim_id,
        project_id=project_id,
        memory_scope_key=studio_id,
        location=location,
    )
    return record.model_dump(mode="json")


@_resilient
def monitor_update(
    monitor_id: str, *, frequency: str | None = None, webhook_url: str | None = None
) -> dict[str, object]:
    """Change a Monitor's frequency and/or webhook."""
    monitor_client.update(monitor_id, frequency=frequency, webhook_url=webhook_url)  # type: ignore[arg-type]
    return {"monitor_id": monitor_id, "updated": True}


@_resilient
def monitor_cancel(monitor_id: str) -> dict[str, object]:
    """Cancel a Monitor — called when a claim is cleared by a human or the project archives."""
    monitor_client.cancel(monitor_id)
    return {"monitor_id": monitor_id, "cancelled": True}


@_resilient
def memory_retrieve(query: str, scope_key: str, *, limit: int = 10) -> dict[str, object]:
    """Search Parallel Memory for prior Task/Monitor results in this studio's scope —
    optional pre-check before a fresh search/task run. Returns an empty list if memory
    is unavailable, never raises."""
    hits = memory_client.retrieve(query, scope_key, limit=limit)
    return {"hits": [h.model_dump(mode="json") for h in hits]}
