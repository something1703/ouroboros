"""FactAgent — ADK_AGENTS.md §3.1. Verifies `event`/`statistic`/`attribution` claims:
`parallel.responses` first (fast, ~15-20s sync), escalating to `parallel.task_run` only
when the quick pass isn't good enough. Mirrors `clear/specialist.py`'s shape (a thin
`LlmAgent` whose only tool is this deterministic batch algorithm) but the escalation
ladder itself is TRUE-CUT-specific (ADK_AGENTS.md §3.1), not CLEAR's.
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
from packages.claims.models import Citation, FieldBasis
from packages.common.logging import get_logger
from packages.parallel_client import responses as responses_client
from packages.parallel_client.task import TaskResult, build_input
from packages.parallel_client.task import run as run_task

log = get_logger(__name__)

# ADK_AGENTS.md §3.1: "Responses is sync ~15-20s" — a claim spends most of its time
# blocked on one HTTP call, not doing local work, so a higher concurrency than CLEAR's
# Task-heavy loop (_CONCURRENCY=2 there, docs/DECISIONS.md #060) is both safe and the
# explicit spec value.
_CONCURRENCY = 8

# ADK_AGENTS.md §3.1: "transcript window ±20s".
_CONTEXT_WINDOW_MS = 20_000

_FACTUAL_CLAIM_SPEC = "factual_claim"


def _build_context(asset_id: str, t_start_ms: int, t_end_ms: int) -> str:
    """The claim's own transcript window: every stored segment overlapping
    `[t_start_ms - 20s, t_end_ms + 20s]`, in order. Segments are read whole (a cut's
    full transcript is a handful of KB even for a long video) and windowed here in
    code — deterministic filtering, not something worth an LLM turn."""
    raw = ledger.get_asset_segments(asset_id=asset_id)
    segments = json.loads(raw).get("segments") or [] if raw else []
    window_start = t_start_ms - _CONTEXT_WINDOW_MS
    window_end = t_end_ms + _CONTEXT_WINDOW_MS
    in_window = [
        s for s in segments if s["t_end_ms"] >= window_start and s["t_start_ms"] <= window_end
    ]
    in_window.sort(key=lambda s: s["t_start_ms"])
    lines = []
    for s in in_window:
        speaker = f"{s['speaker']}: " if s.get("speaker") else ""
        lines.append(f"[{s['t_start_ms'] / 1000:.1f}s] {speaker}{s['transcript']}")
    return "\n".join(lines)


def _confidence_from_citations(count: int) -> Confidence:
    """The Responses API returns citations/annotations, not a Task-style per-field
    `Basis` with its own confidence — there is nothing else to derive a confidence
    signal from. More independently-cited sources backing an answer is a reasonable,
    defensible proxy: zero citations means the model asserted a verdict with nothing
    to point to (low), a few is a normal well-supported quick answer (medium), several
    is unusually well corroborated for a fast pass (high)."""
    if count == 0:
        return Confidence.LOW
    if count <= 2:
        return Confidence.MEDIUM
    return Confidence.HIGH


def _needs_task_escalation(verdict: str, confidence: Confidence, priority: int) -> bool:
    """ADK_AGENTS.md §3.1 step 1: escalate to Task when the quick Responses pass isn't
    trustworthy enough on its own — either the verdict itself is weak
    (`unverifiable`/`contradicted` with low confidence) or the claim is important
    enough (`priority<=2`) that a fast-only pass isn't sufficient regardless of how
    confident it looked."""
    if verdict in ("unverifiable", "contradicted") and confidence == Confidence.LOW:
        return True
    return priority <= 2


def _needs_pro_escalation(confidence: Confidence, priority: int) -> bool:
    """ADK_AGENTS.md §3.1: "if still low and priority 1 -> pro" — the second escalation
    step, evaluated against the Task (not Responses) confidence."""
    return confidence == Confidence.LOW and priority == 1


def _basis_from_responses(
    result: responses_client.ResponsesResult, *, confidence: Confidence
) -> list[FieldBasis]:
    citations: list[Citation] = list(result.citations)
    return [
        FieldBasis(
            field="verdict",
            citations=citations,
            reasoning=str(result.answer.get("key_evidence_summary", "")),
            confidence=confidence,
        )
    ]


def _verify_one_claim(
    claim_id: str, *, project_id: str, studio_id: str, jurisdictions: list[str]
) -> str:
    """Runs the Responses-first, Task-escalation algorithm for one claim (blocking —
    run under `asyncio.to_thread`). Returns 'verified' or 'escalated'."""
    check_budget(project_id)

    claim_row = json.loads(ledger.get_claim(claim_id=claim_id))
    claim_text: str = claim_row["claim_text"]
    priority: int = claim_row["priority"]
    source: dict[str, object] = claim_row.get("source") or {}
    asset_id = str(source.get("asset_id") or "")
    t_start_ms = int(str(source.get("t_start_ms") or 0))
    t_end_ms = int(str(source.get("t_end_ms") or t_start_ms))
    excerpt = str(source.get("excerpt") or "")

    context = _build_context(asset_id, t_start_ms, t_end_ms) if asset_id else ""
    question = (
        f"Claim: {claim_text}\n"
        f"Transcript/on-screen text window (±20s around the claim):\n{context}\n"
        f"Exact excerpt that produced this claim: {excerpt}"
    )

    total_cost = check_and_record_cost(
        project_id, claim_id, api="responses", sku="responses.medium"
    )
    responses_result = responses_client.ask(
        question, schema="factual_quick", effort="medium", claim_id=claim_id
    )
    answer = responses_result.answer
    verdict = str(answer["verdict"])
    responses_confidence = _confidence_from_citations(len(responses_result.citations))

    if not _needs_task_escalation(verdict, responses_confidence, priority):
        write_evidence(
            claim_id,
            method="responses",
            content=answer,
            basis=_basis_from_responses(responses_result, confidence=responses_confidence),
            confidence=responses_confidence,
            cost_usd=total_cost,
        )
        set_status(claim_id, "verified", note=f"FactAgent: {verdict} via responses")
        return "verified"

    mcp_servers = toolbox_mcp_servers()
    top_urls = [c.url for c in responses_result.citations[:5]]
    task_input = build_input(
        claim_text, jurisdictions=jurisdictions, excerpt=excerpt, top_urls=top_urls
    )
    total_cost += check_and_record_cost(project_id, claim_id, api="task", sku="task.core-fast")
    result = run_task(
        task_input,
        _FACTUAL_CLAIM_SPEC,
        claim_id=claim_id,
        project_id=project_id,
        processor="core-fast",
        mcp_servers=mcp_servers,
        memory_scope_key=studio_id,
    )
    assert isinstance(result, TaskResult)

    status = "verified"
    if _needs_pro_escalation(result.overall_confidence, priority):
        total_cost += check_and_record_cost(project_id, claim_id, api="task", sku="task.pro")
        escalated_result = run_task(
            task_input,
            _FACTUAL_CLAIM_SPEC,
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
        claim_id,
        status,
        note=f"FactAgent: {content.get('verdict')} via {result.processor}",
    )
    return status


async def verify_fact_batch(
    claim_ids: list[str], *, project_id: str, studio_id: str, jurisdictions: list[str]
) -> dict[str, object]:
    """ADK_AGENTS.md §3.1's shared algorithm, `_CONCURRENCY`-bounded. One claim's
    failure is isolated — recorded as `error` and never aborts the batch."""
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
                    project_id=project_id,
                    studio_id=studio_id,
                    jurisdictions=jurisdictions,
                )
                (verified if status == "verified" else escalated).append(claim_id)
            except Exception as exc:
                log.error("fact_claim_failed", claim_id=claim_id, error=str(exc))
                errors.append({"claim_id": claim_id, "error": str(exc)})
                try:
                    await asyncio.to_thread(set_status, claim_id, "error", note=str(exc)[:500])
                except Exception:
                    log.error("fact_status_write_failed", claim_id=claim_id)

    await asyncio.gather(*(_one(claim_id) for claim_id in claim_ids))
    return {"verified": verified, "escalated": escalated, "errors": errors}


def _instruction(ctx: ReadonlyContext) -> str:
    return render(
        "fact_agent",
        project_id=ctx.state.get("project_id", ""),
        studio_id=ctx.state.get("studio_id", ""),
        jurisdictions=", ".join(ctx.state.get("jurisdictions", [])),
    )


fact_agent = LlmAgent(
    name="FactAgent",
    model=resilient_model("gemini-3.5-flash"),
    instruction=_instruction,
    tools=[ledger.list_claims, verify_fact_batch],
    output_schema=SpecialistOutput,
    output_key="fact_results",
)
