"""ArchiveAgent — ADK_AGENTS.md §3.2, PHASE_06.md §6.2. Verifies `archival`/`identity`
claims: find the original source of footage/photo/audio via Search, read provenance
off the top candidate pages via Extract, then structure the rights picture with one
Task run. Single-pass (no escalation ladder, unlike FactAgent/CLEAR's specialists) —
neither ADK_AGENTS.md §3.2 nor PHASE_06.md §6.2 describes one.
"""

from __future__ import annotations

import asyncio
import json

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.ouroboros.clear.schemas import SpecialistOutput
from agents.ouroboros.prompts.render import render
from agents.ouroboros.tools import ledger
from agents.ouroboros.tools.budget import check_and_record_cost, check_budget
from agents.ouroboros.tools.evidence import set_status, write_evidence
from agents.ouroboros.tools.mcp import toolbox_mcp_servers
from agents.ouroboros.tools.resilience import resilient_model
from packages.claims.enums import Confidence
from packages.common.logging import get_logger
from packages.parallel_client.extract import extract
from packages.parallel_client.search import SearchHit, search
from packages.parallel_client.task import TaskResult, build_input
from packages.parallel_client.task import run as run_task

log = get_logger(__name__)

# Same weight class as CLEAR's specialists (search + [extract] + task per claim,
# docs/DECISIONS.md #060), not FactAgent's lighter Responses-first loop.
_CONCURRENCY = 2

_ARCHIVE_TASK_SPEC = "legal_location_artwork"
_EXTRACT_MD_MAX_CHARS = 20_000

# PHASE_06.md §6.2: a ranking heuristic for which Search hits are most likely to be a
# real archival source/catalog page, not an `include_domains` filter -- a genuine
# source is never *excluded* just for living on a domain not in this list, it's simply
# not preferred when ranking which of the (up to 10) hits to spend an Extract call on.
_ARCHIVE_LIKE_DOMAINS = (
    "archive.org",
    "gettyimages.com",
    "apimages.com",
    "britishpathe.com",
    "criticalpast.com",
    "nara.gov",
    "loc.gov",
    "bfi.org.uk",
)


def _rank_archive_urls(hits: list[SearchHit], *, limit: int) -> list[str]:
    def _is_archive_like(hit: SearchHit) -> bool:
        return any(domain in hit.url for domain in _ARCHIVE_LIKE_DOMAINS)

    ranked = sorted(hits, key=lambda h: 0 if _is_archive_like(h) else 1)
    return [h.url for h in ranked[:limit]]


def _verify_one_claim(
    claim_id: str, *, project_id: str, studio_id: str, jurisdictions: list[str]
) -> str:
    """Runs the Search -> Extract -> Task algorithm for one claim (blocking — run
    under `asyncio.to_thread`). Always returns 'verified' — see module docstring on
    why there's no escalation path here."""
    check_budget(project_id)

    claim_row = json.loads(ledger.get_claim(claim_id=claim_id))
    entity_text: str = claim_row["entity_text"]
    claim_text: str = claim_row["claim_text"]
    source: dict[str, object] = claim_row.get("source") or {}
    excerpt = str(source.get("excerpt") or "")

    objective = (
        "Find the original source, catalog entry, or rights holder for this "
        f"footage/photo/audio: '{entity_text}'."
    )
    queries = [
        f"{entity_text} archival footage source",
        f"{entity_text} original footage rights holder",
    ]

    total_cost = check_and_record_cost(project_id, claim_id, api="search", sku="search.fast")
    search_result = search(objective, queries, claim_id=claim_id)
    urls = _rank_archive_urls(search_result.hits, limit=3)

    if not urls:
        write_evidence(
            claim_id,
            method="search",
            content={
                "note": "no archive-like source candidate found",
                "search_id": search_result.search_id,
            },
            basis=[],
            confidence=Confidence.LOW,
            cost_usd=total_cost,
        )
        set_status(claim_id, "verified", note="ArchiveAgent: no archival source candidates found")
        return "verified"

    total_cost += check_and_record_cost(
        project_id, claim_id, api="extract", sku="extract.per_url", units=len(urls)
    )
    extract_hits = extract(
        urls,
        objective="provenance, date, rights holder, licensing terms",
        full_content=True,
        claim_id=claim_id,
    )
    extract_md = "\n\n---\n\n".join(
        f"# {hit.url}\n{hit.markdown or chr(10).join(hit.excerpts)}" for hit in extract_hits
    )[:_EXTRACT_MD_MAX_CHARS]

    mcp_servers = toolbox_mcp_servers()
    task_input = build_input(
        claim_text, jurisdictions=jurisdictions, excerpt=excerpt, top_urls=urls
    )
    total_cost += check_and_record_cost(project_id, claim_id, api="task", sku="task.core-fast")
    result = run_task(
        task_input,
        _ARCHIVE_TASK_SPEC,
        claim_id=claim_id,
        project_id=project_id,
        processor="core-fast",
        mcp_servers=mcp_servers,
        memory_scope_key=studio_id,
    )
    assert isinstance(result, TaskResult)

    content: dict[str, object] = (
        result.content if isinstance(result.content, dict) else {"text": result.content}
    )
    content["extract_md"] = extract_md

    write_evidence(
        claim_id,
        method="extract",
        content=content,
        basis=result.basis,
        confidence=result.overall_confidence,
        cost_usd=total_cost,
        parallel_run_id=result.run_id,
        processor=result.processor,
    )
    set_status(claim_id, "verified", note=f"ArchiveAgent: structured via {result.processor}")
    return "verified"


async def verify_archive_batch(
    claim_ids: list[str], *, project_id: str, studio_id: str, jurisdictions: list[str]
) -> dict[str, object]:
    """ADK_AGENTS.md §3.2's shared algorithm, `_CONCURRENCY`-bounded. One claim's
    failure is isolated — recorded as `error` and never aborts the batch."""
    semaphore = asyncio.Semaphore(_CONCURRENCY)
    verified: list[str] = []
    errors: list[dict[str, str]] = []

    async def _one(claim_id: str) -> None:
        async with semaphore:
            try:
                await asyncio.to_thread(
                    _verify_one_claim,
                    claim_id,
                    project_id=project_id,
                    studio_id=studio_id,
                    jurisdictions=jurisdictions,
                )
                verified.append(claim_id)
            except Exception as exc:
                log.error("archive_claim_failed", claim_id=claim_id, error=str(exc))
                errors.append({"claim_id": claim_id, "error": str(exc)})
                try:
                    await asyncio.to_thread(set_status, claim_id, "error", note=str(exc)[:500])
                except Exception:
                    log.error("archive_status_write_failed", claim_id=claim_id)

    await asyncio.gather(*(_one(claim_id) for claim_id in claim_ids))
    return {"verified": verified, "escalated": [], "errors": errors}


def _instruction(ctx: ReadonlyContext) -> str:
    return render(
        "archive_agent",
        project_id=ctx.state.get("project_id", ""),
        studio_id=ctx.state.get("studio_id", ""),
        jurisdictions=", ".join(ctx.state.get("jurisdictions", [])),
    )


archive_agent = LlmAgent(
    name="ArchiveAgent",
    model=resilient_model("gemini-3.5-flash"),
    instruction=_instruction,
    tools=[ledger.list_claims, verify_archive_batch],
    output_schema=SpecialistOutput,
    output_key="archive_results",
)
