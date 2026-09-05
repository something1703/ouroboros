"""Reporter — ADK_AGENTS.md §2.4. LlmAgent: per-claim summaries, Monitor creation,
project summary refresh.

Shared verbatim by TRUE CUT (ADK_AGENTS.md §3: "same classes with kind=factual
behaviour switches in their prompts") — the prompt itself is kind-aware (see
prompts/reporter.md), no Python fork needed. ADK gives every agent instance at most one
`parent_agent`, so CLEAR and TRUECUT each need their own instance;
`build_reporter_agent()` is the one construction path both pipelines call."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.genai import types

from agents.ouroboros.clear.schemas import ReporterOutput
from agents.ouroboros.prompts.render import render
from agents.ouroboros.tools import ledger
from agents.ouroboros.tools.firestore_tools import write_claim_summary, write_project_summary
from agents.ouroboros.tools.parallel_tools import monitor_create_snapshot, monitor_create_stream
from agents.ouroboros.tools.reporter_tools import gather_report_inputs
from agents.ouroboros.tools.resilience import resilient_model
from config.parallel import frequency_for

_MONITOR_TOOL_NAMES = {"monitor_create_snapshot", "monitor_create_stream"}


def _days_to_release(release_date_iso: object) -> int:
    if not isinstance(release_date_iso, str) or not release_date_iso:
        return 999  # unknown release date -> treat as far off, least-aggressive cadence
    release = date.fromisoformat(release_date_iso[:10])
    return max((release - datetime.now(UTC).date()).days, 0)


def _record_monitor_and_count(
    *, tool: BaseTool, args: dict[str, Any], tool_context: Any, tool_response: dict[str, Any]
) -> None:
    """Persists a real Monitor to the ledger and tracks how many actually succeeded
    this run — ground truth for `_finalize_report` below, since the model's own
    `monitors_created` count can't be trusted (see its docstring)."""
    if tool.name not in _MONITOR_TOOL_NAMES or "error" in tool_response:
        return None
    ledger.record_monitor(
        monitor_id=tool_response["monitor_id"],
        claim_id=tool_response["claim_id"],
        monitor_type=tool_response["type"],
        task_run_id=tool_response.get("task_run_id") or "",
        query=tool_response.get("query") or "",
        frequency=tool_response["frequency"],
        status=tool_response["status"],
    )
    tool_context.state["_monitors_created_count"] = (
        tool_context.state.get("_monitors_created_count", 0) + 1
    )
    return None


def _finalize_report(*, callback_context: CallbackContext) -> None:
    """Overwrites the model's own `monitors_created`/`claims_by_risk` tallies with
    ground truth computed from real tool results and RiskAssessor's own output,
    rather than trusting the model's arithmetic — found live: with 4 already-scored
    claims and 2 real (failed) Monitor attempts, the model reported `monitors_created:
    2` (miscounting *attempts* as *successes*) and `claims_by_risk: {}` (an empty
    tally despite an explicit prompt instruction to compute it) in the same run.
    Both values are pure aggregation with no judgment involved, so code can compute
    them exactly instead of hoping the model counts correctly."""
    report = callback_context.state.get("report")
    if not isinstance(report, dict):
        return None
    risks = callback_context.state.get("risks", {}).get("risks", [])
    claims_by_risk: dict[str, int] = {}
    for risk in risks:
        level = risk.get("level")
        if level:
            claims_by_risk[level] = claims_by_risk.get(level, 0) + 1
    report["claims_by_risk"] = claims_by_risk
    report["monitors_created"] = callback_context.state.get("_monitors_created_count", 0)
    callback_context.state["report"] = report
    return None


def _instruction(ctx: ReadonlyContext) -> str:
    base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8080")
    jurisdictions = ctx.state.get("jurisdictions", [])
    return render(
        "reporter",
        project_id=ctx.state.get("project_id", ""),
        studio_id=ctx.state.get("studio_id", ""),
        webhook_url=f"{base_url}/webhooks/parallel/monitor",
        monitor_frequency=frequency_for(_days_to_release(ctx.state.get("release_date"))),
        primary_territory=jurisdictions[0] if jurisdictions else "",
    )


def build_reporter_agent() -> LlmAgent:
    return LlmAgent(
        name="Reporter",
        model=resilient_model("gemini-3.1-pro-preview"),
        instruction=_instruction,
        tools=[
            ledger.list_claims,
            gather_report_inputs,
            write_claim_summary,
            monitor_create_snapshot,
            monitor_create_stream,
            write_project_summary,
        ],
        generate_content_config=types.GenerateContentConfig(temperature=0.3),
        output_schema=ReporterOutput,
        output_key="report",
        after_tool_callback=_record_monitor_and_count,
        after_agent_callback=_finalize_report,
    )


reporter_agent = build_reporter_agent()
