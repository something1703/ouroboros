"""AskOuroboros — ADK_AGENTS.md §4. Grounded Q&A over the claim ledger, the studio's
private corpus, and live web search (PHASE_08.md §8.4). Named exactly "AskOuroboros"
so OuroborosCoordinator's `transfer_to_agent` can find it by name."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.ouroboros.prompts.render import render
from agents.ouroboros.tools import ledger
from agents.ouroboros.tools.corpus_tools import search_private_corpus
from agents.ouroboros.tools.grounding_tools import ask_grounded
from agents.ouroboros.tools.resilience import resilient_model


def _instruction(ctx: ReadonlyContext) -> str:
    return render("ask_ouroboros", question=ctx.state.get("question", ""))


ask_ouroboros_agent = LlmAgent(
    name="AskOuroboros",
    model=resilient_model("gemini-3.5-flash"),
    instruction=_instruction,
    tools=[
        ledger.get_claim,
        ledger.list_claims,
        ledger.get_prior_decisions,
        search_private_corpus,
        ask_grounded,
    ],
)
