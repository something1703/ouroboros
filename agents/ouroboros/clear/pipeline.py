"""CLEAR — ADK_AGENTS.md §2: SequentialAgent tying ClaimTriage -> ClearFanOut ->
RiskAssessor -> Reporter."""

from __future__ import annotations

from google.adk.agents import SequentialAgent

from agents.ouroboros.clear.fan_out import clear_fan_out_agent
from agents.ouroboros.clear.reporter import reporter_agent
from agents.ouroboros.clear.risk_assessor import risk_assessor_agent
from agents.ouroboros.clear.triage import claim_triage_agent

clear_agent = SequentialAgent(
    name="CLEAR",
    sub_agents=[claim_triage_agent, clear_fan_out_agent, risk_assessor_agent, reporter_agent],
)
