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
from decimal import Decimal

from agents.ouroboros.tools import ledger
from agents.ouroboros.tools.mcp import toolbox_mcp_servers
from packages.claims.enums import ClaimCategory, Confidence
from packages.claims.models import FieldBasis
from packages.common.errors import BudgetExceeded
from packages.common.ids import new_ulid
from packages.common.logging import get_logger
from packages.parallel_client.cost import price_for
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


def _current_cycle(claim_id: str) -> int:
    raw = ledger.get_claim(claim_id=claim_id)
    row = json.loads(raw) if raw else None
    if not row or row.get("cycle") is None:
        return 0
    return int(row["cycle"])


def _write_evidence(
    claim_id: str,
    *,
    method: str,
    content: dict[str, object],
    basis: Sequence[FieldBasis],
    confidence: Confidence,
    cost_usd: Decimal,
    parallel_run_id: str | None = None,
    processor: str | None = None,
) -> None:
    expected_cycle = _current_cycle(claim_id) + 1
    ledger.record_evidence(
        evidence_id=new_ulid(),
        claim_id=claim_id,
        expected_cycle=expected_cycle,
        method=method,
        output_json=json.dumps(content),
        basis_json=json.dumps([b.model_dump(mode="json") for b in basis]),
        overall_confidence=confidence.value,
        cost_usd=float(cost_usd),
        parallel_run_id=parallel_run_id or "",
        processor=processor or "",
    )


def _check_budget(project_id: str) -> None:
    """Raises `BudgetExceeded` if the project is *already* over its cap. Toolbox-routed
    (not a direct DB read via `packages.parallel_client.cost.check_budget`) — found
    live, the deployed Agent Engine's runtime has no VPC path to Cloud SQL's private
    IP, unlike Toolbox (a properly VPC-connected Cloud Run service), so a direct
    SQLAlchemy connection from inside the agent process just hangs until timeout no
    matter how large `max_connections` is (docs/DECISIONS.md #062)."""
    row = json.loads(ledger.check_budget(project_id=project_id))
    if Decimal(str(row["spend_usd"])) > Decimal(str(row["cap_usd"])):
        raise BudgetExceeded(project_id, float(row["spend_usd"]), float(row["cap_usd"]))


def _check_and_record_cost(project_id: str, claim_id: str, *, api: str, sku: str) -> Decimal:
    """Pre-flight budget check + cost reservation for one priced Parallel call —
    Toolbox-routed equivalent of `packages.parallel_client.cost.CostMeter` (see
    `_check_budget` above for why). Skips `CostMeter`'s BigQuery streaming and
    post-hoc `record_actual` correction: a best-effort analytics mirror, not needed
    for the budget-enforcement behavior this replaces."""
    estimated_cost = price_for(sku)
    row = json.loads(ledger.check_budget(project_id=project_id))
    spend = Decimal(str(row["spend_usd"]))
    cap = Decimal(str(row["cap_usd"]))
    if spend + estimated_cost > cap:
        raise BudgetExceeded(project_id, float(spend), float(cap))
    ledger.record_cost(
        project_id=project_id,
        claim_id=claim_id,
        api=api,
        sku=sku,
        units=1,
        cost_usd=float(estimated_cost),
    )
    return estimated_cost


def _set_status(claim_id: str, status: str, *, note: str) -> None:
    ledger.set_status(
        claim_id=claim_id,
        new_status=status,
        actor="agent",
        note=note,
        ref_json="{}",
        event_id=new_ulid(),
    )


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
    _check_budget(project_id)

    claim_row = json.loads(ledger.get_claim(claim_id=claim_id))
    category = ClaimCategory(claim_row["category"])
    entity_text: str = claim_row["entity_text"]
    claim_text: str = claim_row["claim_text"]
    priority: int = claim_row["priority"]
    source: dict[str, object] = claim_row.get("source") or {}
    excerpt = str(source.get("excerpt") or "")

    objective, queries = build_objective(category, entity_text, jurisdictions)
    location = jurisdictions[0] if jurisdictions else None

    total_cost = _check_and_record_cost(project_id, claim_id, api="search", sku="search.fast")
    search_result = search(
        objective, queries, category=category, location=location, claim_id=claim_id
    )

    if priority >= 4 and _looks_public_domain(search_result.hits):
        _write_evidence(
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
        _set_status(
            claim_id, "verified", note="search-only: obvious public-domain/no-rights signal"
        )
        return "verified"

    top_urls = [hit.url for hit in search_result.hits[:5]]
    task_input = build_input(
        claim_text, jurisdictions=jurisdictions, excerpt=excerpt, top_urls=top_urls
    )

    mcp_servers = toolbox_mcp_servers()
    total_cost += _check_and_record_cost(project_id, claim_id, api="task", sku="task.core-fast")
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
        total_cost += _check_and_record_cost(project_id, claim_id, api="task", sku="task.pro")
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

    _write_evidence(
        claim_id,
        method="task",
        content=content,
        basis=result.basis,
        confidence=result.overall_confidence,
        cost_usd=total_cost,
        parallel_run_id=result.run_id,
        processor=result.processor,
    )
    _set_status(
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
                await asyncio.to_thread(_set_status, claim_id, "pending", note="budget exceeded")
            except Exception as exc:
                log.error("specialist_claim_failed", claim_id=claim_id, error=str(exc))
                errors.append({"claim_id": claim_id, "error": str(exc)})
                try:
                    await asyncio.to_thread(_set_status, claim_id, "error", note=str(exc)[:500])
                except Exception:
                    log.error("specialist_status_write_failed", claim_id=claim_id)

    await asyncio.gather(*(_one(claim_id) for claim_id in claim_ids))
    return {"verified": verified, "escalated": escalated, "errors": errors}
