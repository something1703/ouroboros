"""TRUECUT — ADK_AGENTS.md §3: SequentialAgent tying ClaimTriage -> FactAgent ->
ArchiveAgent -> RiskAssessor -> Reporter. FactAgent and ArchiveAgent run sequentially
(not fanned out like CLEAR's four specialists) — ADK_AGENTS.md §3's own sub_agents
list, no ParallelAgent wrapper for these two.

ClaimTriage/RiskAssessor/Reporter are "the same classes" as CLEAR's (ADK_AGENTS.md §3)
but need their own instances here — ADK allows at most one `parent_agent` per agent
object, so this calls each one's `build_*_agent()` factory again rather than importing
CLEAR's already-parented singletons.
"""

from __future__ import annotations

from google.adk.agents import SequentialAgent

from agents.ouroboros.clear.reporter import build_reporter_agent
from agents.ouroboros.clear.risk_assessor import build_risk_assessor_agent
from agents.ouroboros.clear.triage import build_claim_triage_agent
from agents.ouroboros.truecut.archive import archive_agent
from agents.ouroboros.truecut.fact import fact_agent

truecut_agent = SequentialAgent(
    name="TRUECUT",
    sub_agents=[
        build_claim_triage_agent(),
        fact_agent,
        archive_agent,
        build_risk_assessor_agent(),
        build_reporter_agent(),
    ],
)
