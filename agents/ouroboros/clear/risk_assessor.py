"""RiskAssessor — ADK_AGENTS.md §2.3. LlmAgent: reads the deterministic pre-score
(packages/claims/risk.prescore, via the gather_risk_inputs tool) and may adjust it ±1
level with a written rationale — real judgment, not a passthrough.

Shared verbatim by TRUE CUT (ADK_AGENTS.md §3: "same classes with kind=factual
behaviour switches in their prompts") — the prompt itself is kind-aware (see
prompts/risk_assessor.md) and `prescore()` already dispatches on `claim.kind`, no
Python fork needed. ADK gives every agent instance at most one `parent_agent`, so
CLEAR and TRUECUT each need their own instance; `build_risk_assessor_agent()` is the
one construction path both pipelines call."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types

from agents.ouroboros.clear.schemas import RiskAssessorOutput
from agents.ouroboros.prompts.render import render
from agents.ouroboros.tools import ledger
from agents.ouroboros.tools.firestore_tools import write_claim_view
from agents.ouroboros.tools.resilience import resilient_model
from agents.ouroboros.tools.risk_tools import gather_risk_inputs


def _instruction(ctx: ReadonlyContext) -> str:
    return render(
        "risk_assessor",
        project_id=ctx.state.get("project_id", ""),
        jurisdictions=", ".join(ctx.state.get("jurisdictions", [])),
        release_date=ctx.state.get("release_date") or "unset",
    )


def build_risk_assessor_agent() -> LlmAgent:
    return LlmAgent(
        name="RiskAssessor",
        model=resilient_model("gemini-3.1-pro-preview"),
        instruction=_instruction,
        tools=[ledger.list_claims, gather_risk_inputs, ledger.record_risk, write_claim_view],
        generate_content_config=types.GenerateContentConfig(temperature=0.3),
        output_schema=RiskAssessorOutput,
        output_key="risks",
    )


risk_assessor_agent = build_risk_assessor_agent()
