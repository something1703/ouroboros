"""`root_agent` — ADK_AGENTS.md §1. `adk web`/`adk run` discover this module."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.ouroboros.clear.pipeline import clear_agent
from agents.ouroboros.prompts.render import render
from agents.ouroboros.tools.resilience import resilient_model
from agents.ouroboros.tools.session_tools import initialize_run
from agents.ouroboros.truecut.pipeline import truecut_agent


def _instruction(_ctx: ReadonlyContext) -> str:
    return render("coordinator")


root_agent = LlmAgent(
    name="OuroborosCoordinator",
    model=resilient_model("gemini-3.5-flash"),
    instruction=_instruction,
    tools=[initialize_run],
    sub_agents=[clear_agent, truecut_agent],
)
