"""Shared specialist algorithm — ADK_AGENTS.md §2.2. The four category agents
(MusicAgent, BrandAgent, PersonAgent, LocationArtAgent — see the sibling `music.py`,
`brand.py`, `person.py`, `location_art.py`) are thin `LlmAgent`s whose only tool is a
category-specific async wrapper around `verify_batch` below; the 7-step algorithm
itself is deterministic code. Search objectives/queries already
come from `packages.parallel_client.search.build_objective` (a deterministic template,
not an LLM call) and escalation from `packages.parallel_client.task.should_escalate` (a
deterministic threshold) — both built and verified live in Phase 4 — so there is no
per-claim LLM judgment left to delegate into the loop; the specialist LlmAgent's real
job is reading its assigned batch out of session state and reporting the outcome.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence

from agents.ouroboros.tools import ledger
from agents.ouroboros.tools.budget import check_and_record_cost, check_budget
from agents.ouroboros.tools.evidence import set_status, write_evidence
from agents.ouroboros.tools.mcp import toolbox_mcp_servers
from packages.claims.enums import ClaimCategory, Confidence
from packages.common.errors import BudgetExceeded
from packages.common.logging import get_logger
from packages.parallel_client.search import SearchHit, build_objective, search
from packages.parallel_client.task import TaskResult, build_input, should_escalate
from packages.parallel_client.task import run as run_task

log = get_logger(__name__)

# A per-specialist semaphore; all four specialists' ParallelAgent fan-out runs
# concurrently, so the real system-wide ceiling is 4x this number of claims in flight
# at once. Kept modest (docs/DECISIONS.md #060) since every claim still makes several
# real Toolbox round trips (check_budget, record_cost x1-3, record_evidence, set_status).
_CONCURRENCY = 2

# A cheap, deterministic pre-filter for step 3's "obvious public-domain/no-rights-needed
# signal" — a keyword heuristic over search excerpts rather than a second LLM call.
# False negatives just mean the (more expensive but always-correct) Task run happens
# anyway; a false positive would wrongly skip the Task, so the bar is a direct phrase
# match, not a fuzzy one.
_PUBLIC_DOMAIN_PHRASES = (
    "public domain",
    "no license required",
    "no permission required",
    "royalty-free",
    "royalty free",
    "no rights reserved",
)

AugmentFn = Callable[[dict[str, object], dict[str, object]], dict[str, object]]


def _looks_public_domain(hits: Sequence[SearchHit]) -> bool:
    for hit in hits:
        for excerpt in hit.excerpts:
            lowered = excerpt.lower()
            if any(phrase in lowered for phrase in _PUBLIC_DOMAIN_PHRASES):
                return True
    return False


def _verify_one_claim(
    claim_id: str,
    *,
    spec_name: str,
    project_id: str,
    studio_id: str,
    jurisdictions: list[str],
    augment: AugmentFn | None,
) -> str:
    """Runs the full 7-step algorithm for one claim (blocking — run under
    `asyncio.to_thread`). Returns 'verified' or 'escalated'.

    `category` is read from the claim's own ledger row, not a parameter — a batch can
    mix categories that share one spec (`location` + `artwork` both use
    `legal_location_artwork`), and `build_objective`'s per-category template must match
    each claim's *real* category, not the batch's spec choice.
    """
    check_budget(project_id)

    claim_row = json.loads(ledger.get_claim(claim_id=claim_id))
    category = ClaimCategory(claim_row["category"])
    entity_text: str = claim_row["entity_text"]
    claim_text: str = claim_row["claim_text"]
    priority: int = claim_row["priority"]
    source: dict[str, object] = claim_row.get("source") or {}
    excerpt = str(source.get("excerpt") or "")

    objective, queries = build_objective(category, entity_text, jurisdictions)
    location = jurisdictions[0] if jurisdictions else None

    total_cost = check_and_record_cost(project_id, claim_id, api="search", sku="search.fast")
    search_result = search(
        objective, queries, category=category, location=location, claim_id=claim_id
    )

    if priority >= 4 and _looks_public_domain(search_result.hits):
        write_evidence(
            claim_id,
            method="search",
            content={
                "signal": "public_domain_or_no_rights_needed",
                "search_id": search_result.search_id,
            },
            basis=[],
            confidence=Confidence.MEDIUM,
            cost_usd=total_cost,
        )
        set_status(claim_id, "verified", note="search-only: obvious public-domain/no-rights signal")
        return "verified"

    top_urls = [hit.url for hit in search_result.hits[:5]]
    task_input = build_input(
        claim_text, jurisdictions=jurisdictions, excerpt=excerpt, top_urls=top_urls
    )

    mcp_servers = toolbox_mcp_servers()
    total_cost += check_and_record_cost(project_id, claim_id, api="task", sku="task.core-fast")
    result = run_task(
        task_input,
        spec_name,
        claim_id=claim_id,
        project_id=project_id,
        processor="core-fast",
        mcp_servers=mcp_servers,
        memory_scope_key=studio_id,
    )
    assert isinstance(result, TaskResult)

    status = "verified"
    if should_escalate(result.overall_confidence, priority):
        total_cost += check_and_record_cost(project_id, claim_id, api="task", sku="task.pro")
        escalated_result = run_task(
            task_input,
            spec_name,
            claim_id=claim_id,
            project_id=project_id,
            processor="pro",
            mcp_servers=mcp_servers,
            memory_scope_key=studio_id,
        )
        assert isinstance(escalated_result, TaskResult)
        result = escalated_result
        status = "escalated"

    content: dict[str, object] = (
        result.content if isinstance(result.content, dict) else {"text": result.content}
    )
    if augment is not None:
        content = augment(claim_row, content)

    write_evidence(
        claim_id,
        method="task",
        content=content,
        basis=result.basis,
        confidence=result.overall_confidence,
        cost_usd=total_cost,
        parallel_run_id=result.run_id,
        processor=result.processor,
    )
    set_status(
        claim_id, status, note=f"{category.value} specialist: {spec_name} via {result.processor}"
    )
    return status


async def verify_batch(
    claim_ids: list[str],
    *,
    spec_name: str,
    project_id: str,
    studio_id: str,
    jurisdictions: list[str],
    augment: AugmentFn | None = None,
) -> dict[str, object]:
    """ADK_AGENTS.md §2.2's shared algorithm, `asyncio.Semaphore(5)`-bounded. One
    claim's failure is isolated — recorded as `error` and never aborts the batch."""
    semaphore = asyncio.Semaphore(_CONCURRENCY)
    verified: list[str] = []
    escalated: list[str] = []
    errors: list[dict[str, str]] = []

    async def _one(claim_id: str) -> None:
        async with semaphore:
            try:
                status = await asyncio.to_thread(
                    _verify_one_claim,
                    claim_id,
                    spec_name=spec_name,
                    project_id=project_id,
                    studio_id=studio_id,
                    jurisdictions=jurisdictions,
                    augment=augment,
                )
                (verified if status == "verified" else escalated).append(claim_id)
            except BudgetExceeded as exc:
                errors.append({"claim_id": claim_id, "error": f"budget_exceeded: {exc}"})
                await asyncio.to_thread(set_status, claim_id, "pending", note="budget exceeded")
            except Exception as exc:
                log.error("specialist_claim_failed", claim_id=claim_id, error=str(exc))
                errors.append({"claim_id": claim_id, "error": str(exc)})
                try:
                    await asyncio.to_thread(set_status, claim_id, "error", note=str(exc)[:500])
                except Exception:
                    log.error("specialist_status_write_failed", claim_id=claim_id)

    await asyncio.gather(*(_one(claim_id) for claim_id in claim_ids))
    return {"verified": verified, "escalated": escalated, "errors": errors}
