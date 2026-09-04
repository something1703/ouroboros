"""ClearFanOut — ADK_AGENTS.md §2.2: runs the four specialists concurrently, each
reading its own batch from `triage.batches.*`."""

from __future__ import annotations

from google.adk.agents import ParallelAgent

from agents.ouroboros.clear.brand import brand_agent
from agents.ouroboros.clear.location_art import location_art_agent
from agents.ouroboros.clear.music import music_agent
from agents.ouroboros.clear.person import person_agent

clear_fan_out_agent = ParallelAgent(
    name="ClearFanOut",
    sub_agents=[music_agent, brand_agent, person_agent, location_art_agent],
)
