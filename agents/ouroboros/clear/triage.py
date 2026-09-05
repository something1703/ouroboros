"""ClaimTriage — ADK_AGENTS.md §2.1. LlmAgent: real judgment (priority rubric),
real tool use (list_claims, get_prior_decisions, set_status), structured output.

Shared verbatim by TRUE CUT (ADK_AGENTS.md §3: "same classes with kind=factual
behaviour switches in their prompts") — the prompt itself is kind-aware (see
prompts/claim_triage.md), no Python fork needed. ADK gives every agent instance at
most one `parent_agent`, so CLEAR and TRUECUT each need their own instance;
`build_claim_triage_agent()` is the one construction path both pipelines call."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.ouroboros.clear.schemas import TriageOutput
from agents.ouroboros.prompts.render import render
from agents.ouroboros.tools import ledger
from agents.ouroboros.tools.resilience import resilient_model


def _instruction(ctx: ReadonlyContext) -> str:
    return render(
        "claim_triage",
        project_id=ctx.state.get("project_id", ""),
        asset_id=ctx.state.get("asset_id", ""),
        studio_id=ctx.state.get("studio_id", ""),
        jurisdictions=", ".join(ctx.state.get("jurisdictions", [])),
        release_date=ctx.state.get("release_date") or "unset",
    )


def build_claim_triage_agent() -> LlmAgent:
    return LlmAgent(
        name="ClaimTriage",
        model=resilient_model("gemini-3.5-flash"),
        instruction=_instruction,
        tools=[ledger.list_claims, ledger.get_prior_decisions, ledger.set_status],
        output_schema=TriageOutput,
        output_key="triage",
    )


claim_triage_agent = build_claim_triage_agent()
