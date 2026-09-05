"""ClearFanOut — ADK_AGENTS.md §2.2: runs the four specialists concurrently, each
sweeping its own category directly via `list_claims(status="triaged", category=...)`
(docs/DECISIONS.md) rather than reading `triage.batches` from session state — found
live that the model didn't reliably execute ClaimTriage's own "also sweep leftover
triaged claims" step across every run, the same class of session-state hand-off
fragility RiskAssessor/Reporter were already fixed for (#074/#075)."""

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
