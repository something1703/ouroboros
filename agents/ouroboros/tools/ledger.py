"""Ledger tools (ADK_AGENTS.md §0) — loaded live from the MCP Toolbox server
(services/toolbox), not reimplemented here. `services/toolbox/tools.yaml` is the source
of truth for each tool's real parameters and SQL; the plain functions below just give
ADK a real, typed, picklable signature to build a `FunctionTool` from.

Each function is a thin call-through to the matching `ToolboxSyncTool`, resolved lazily
(see `_tools()`) rather than handing the raw `ToolboxSyncTool` object to
`LlmAgent(tools=[...])` directly, as an earlier version of this module did. Found live
deploying to Vertex AI Agent Engine: `agent_engines.create()` internally
`copy.deepcopy()`s the whole agent tree, and a `ToolboxSyncTool` carries a live
background thread, its own asyncio event loop, and an open `aiohttp` session (verified
via `vars()`) — none of which survive `deepcopy` (`TypeError: cannot pickle
'_contextvars.Context' object`). A plain function has none of that state; `copy.deepcopy`
treats functions as atomic and returns them unchanged, so wrapping every tool call in one
sidesteps the problem entirely instead of trying to make the SDK's own object copyable.

`ledger_write`'s tools (`record_evidence`, `set_status`, `record_risk`, `record_monitor`)
are never handed to Parallel — only `parallel_readonly` (Phase 5.6) is exposed externally.

Toolbox tools are loaded lazily (behind `_tools()`, cached on first real call) rather than
at import time: this module is transitively imported by pure-logic code (e.g.
`clear/specialist.py`'s `_looks_public_domain`) that offline unit tests need to exercise
without a live Toolbox server reachable — found live, an eager module-level
`load_toolset()` call made every such test's *collection* fail with a connection error
before the test itself ever ran (docs/DECISIONS.md #049).
"""

from __future__ import annotations

from functools import cache
from typing import Any

from packages.ledger.toolbox_client import load_toolset


@cache
def _tools() -> dict[str, Any]:
    read_tools = load_toolset("ledger_read")
    write_tools = load_toolset("ledger_write")
    return {tool.__name__: tool for tool in (*read_tools, *write_tools)}


def get_claim(claim_id: str) -> str:
    """Get one claim by id, with its latest evidence cycle and current risk assessment.
    Returns a JSON object."""
    return str(_tools()["get_claim"](claim_id=claim_id))


def list_claims(
    project_id: str, status: str = "", category: str = "", result_limit: int = 50
) -> str:
    """List claims for a project, optionally filtered by status and/or category. Pass
    an empty string for either filter to skip it. Returns a JSON array; each claim
    includes `kind` (`legal` or `factual`) so a caller can branch on it, and `channel`
    (`dialogue`/`narration`/`on_screen_text`/`visual`/`action_line`/null) for TRUE CUT's
    channel-aware priority rubric (ADK_AGENTS.md §3.3)."""
    return str(
        _tools()["list_claims"](
            project_id=project_id, status=status, category=category, result_limit=result_limit
        )
    )


def get_prior_decisions(studio_id: str, entity_normalized: str) -> str:
    """Studio memory: prior clearance decisions for an entity, most recent first. Used
    to skip re-research when a recent decision already exists. Returns a JSON array."""
    return str(
        _tools()["get_prior_decisions"](studio_id=studio_id, entity_normalized=entity_normalized)
    )


def get_project(project_id: str) -> str:
    """Get one project by id. Returns a JSON object."""
    return str(_tools()["get_project"](project_id=project_id))


def check_budget(project_id: str) -> str:
    """Get a project's total spend so far and its budget cap, so a caller can decide
    whether it's already over budget. Toolbox-routed rather than a direct DB read —
    found live, the deployed Agent Engine's runtime has no VPC path to Cloud SQL's
    private IP, so a direct SQLAlchemy connection from inside the agent process just
    hangs until timeout (docs/DECISIONS.md #062). Returns a JSON object with
    `spend_usd`/`cap_usd`."""
    return str(_tools()["check_budget"](project_id=project_id))


def record_evidence(
    evidence_id: str,
    claim_id: str,
    expected_cycle: int,
    method: str,
    output_json: str,
    basis_json: str,
    overall_confidence: str,
    cost_usd: float,
    parallel_run_id: str = "",
    processor: str = "",
) -> str:
    """Insert a new evidence cycle for a claim. `expected_cycle` must equal (current max
    cycle for this claim) + 1 — the insert is a no-op if it doesn't, guarding against
    writing evidence out of order. `method` is one of: search, task, responses,
    entity_search, extract, grounding. `overall_confidence` is one of: high, medium,
    low, unknown. Pass an empty string for `parallel_run_id`/`processor` when there is
    no Parallel Task run behind this evidence."""
    return str(
        _tools()["record_evidence"](
            evidence_id=evidence_id,
            claim_id=claim_id,
            expected_cycle=expected_cycle,
            method=method,
            output_json=output_json,
            basis_json=basis_json,
            overall_confidence=overall_confidence,
            cost_usd=cost_usd,
            parallel_run_id=parallel_run_id,
            processor=processor,
        )
    )


def set_status(
    claim_id: str, new_status: str, actor: str, note: str, ref_json: str, event_id: str
) -> str:
    """Update a claim's status and append a verification_history entry recording the
    transition. `new_status` is one of: pending, triaged, verifying, verified,
    escalated, error, stale. `actor` is one of: ingest, agent, monitor,
    reverify_worker, human."""
    return str(
        _tools()["set_status"](
            claim_id=claim_id,
            new_status=new_status,
            actor=actor,
            note=note,
            ref_json=ref_json,
            event_id=event_id,
        )
    )


def record_risk(
    claim_id: str,
    evidence_id: str,
    level: str,
    score: float,
    rationale: str,
    cost_band: str,
    remediation_suggested: bool,
    remediation_kind: str,
    territory_flags_json: str,
) -> str:
    """Upsert the current risk assessment for a claim (one row per claim, latest wins)
    and append the same assessment to risk_history (append-only) in one transaction.
    `level` is one of: none, low, medium, high, blocking. `cost_band` is one of: none,
    <1k, 1k-10k, 10k-100k, >100k, unknown (pass an empty string for null/not-assessed).
    `remediation_kind` is one of: replace_brand, replace_music, reshoot, recut,
    obtain_release, none. `territory_flags_json` maps jurisdiction code to risk level,
    as a JSON string ("{}" for none)."""
    return str(
        _tools()["record_risk"](
            claim_id=claim_id,
            evidence_id=evidence_id,
            level=level,
            score=score,
            rationale=rationale,
            cost_band=cost_band,
            remediation_suggested=remediation_suggested,
            remediation_kind=remediation_kind,
            territory_flags_json=territory_flags_json,
        )
    )


def record_monitor(
    monitor_id: str,
    claim_id: str,
    monitor_type: str,
    task_run_id: str,
    query: str,
    frequency: str,
    status: str,
) -> str:
    """Upsert a Parallel Monitor record (one row per monitor_id) — call this after a
    real, successful monitor_create_snapshot/monitor_create_stream call, never for a
    failed one. `monitor_type` is one of: snapshot, event_stream. `task_run_id` is set
    for a snapshot Monitor, `query` for an event_stream one — pass an empty string for
    whichever doesn't apply. `frequency` is one of: 1h, 1d, 1w. `status` is one of:
    active, cancelled."""
    return str(
        _tools()["record_monitor"](
            monitor_id=monitor_id,
            claim_id=claim_id,
            monitor_type=monitor_type,
            task_run_id=task_run_id,
            query=query,
            frequency=frequency,
            status=status,
        )
    )


def record_cost(
    project_id: str, claim_id: str, api: str, sku: str, units: int, cost_usd: float
) -> str:
    """Record one cost_events row (an estimate, or a correction if `sku` ends in
    `.correction`). Toolbox-routed for the same reason as `check_budget` above. Pass
    an empty string for `claim_id` when there is none."""
    return str(
        _tools()["record_cost"](
            project_id=project_id,
            claim_id=claim_id,
            api=api,
            sku=sku,
            units=units,
            cost_usd=cost_usd,
        )
    )


def count_history(claim_id: str) -> str:
    """Count verification_history rows for one claim. Toolbox-routed for the same
    reason as check_budget above (docs/DECISIONS.md #067). Returns a JSON object with
    `count`."""
    return str(_tools()["count_history"](claim_id=claim_id))


def project_status_counts(project_id: str) -> str:
    """Count claims per status for a project. Toolbox-routed (docs/DECISIONS.md #067).
    Returns a JSON array of `{status, count}` rows."""
    return str(_tools()["project_status_counts"](project_id=project_id))


def project_risk_counts(project_id: str) -> str:
    """Count claims per risk level for a project. Toolbox-routed (docs/DECISIONS.md
    #067). Returns a JSON array of `{level, count}` rows."""
    return str(_tools()["project_risk_counts"](project_id=project_id))


def get_asset_segments(asset_id: str) -> str:
    """Get a cut asset's full transcript segments (empty for a script asset). Returns a
    JSON object with `segments`, each `{t_start_ms, t_end_ms, speaker, transcript}` in
    absolute video time. PHASE_06.md §6.1: FactAgent builds a claim's ±20s context
    window from this rather than re-running video understanding per claim."""
    return str(_tools()["get_asset_segments"](asset_id=asset_id))


READ_TOOLS = [
    get_claim,
    list_claims,
    get_prior_decisions,
    get_project,
    check_budget,
    count_history,
    project_status_counts,
    project_risk_counts,
    get_asset_segments,
]
WRITE_TOOLS = [record_evidence, set_status, record_risk, record_monitor, record_cost]
ALL_TOOLS = [*READ_TOOLS, *WRITE_TOOLS]
