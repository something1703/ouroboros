"""Session-initialization tool used only by OuroborosCoordinator. Populates the state
keys every downstream agent reads (ADK_AGENTS.md §1: `project_id`, `asset_id`,
`studio_id`, `jurisdictions`, `release_date`, `run_id`)."""

from __future__ import annotations

import json

from google.adk.tools import ToolContext  # type: ignore[attr-defined]

from packages.common.errors import NotFound
from packages.common.ids import new_ulid

from . import ledger


def initialize_run(
    project_id: str, asset_id: str, tool_context: ToolContext, question: str = ""
) -> dict[str, object]:
    """Look up the project and populate session state for this run
    (studio_id, jurisdictions, release_date, run_id). Must be called before
    transferring to CLEAR, TRUECUT, or AskOuroboros. Pass the input's `question`
    field when (and only when) mode is "ask"; leave it empty otherwise."""
    raw = ledger.get_project(project_id=project_id)
    project = json.loads(raw) if raw else None
    if not project:
        raise NotFound("project", project_id)

    run_id = new_ulid()
    tool_context.state["project_id"] = project_id
    tool_context.state["asset_id"] = asset_id
    tool_context.state["studio_id"] = project["studio_id"]
    tool_context.state["jurisdictions"] = project.get("distribution_territories") or []
    tool_context.state["release_date"] = project.get("release_date")
    tool_context.state["run_id"] = run_id
    tool_context.state["question"] = question

    return {
        "run_id": run_id,
        "studio_id": project["studio_id"],
        "jurisdictions": project.get("distribution_territories") or [],
        "release_date": project.get("release_date"),
    }
