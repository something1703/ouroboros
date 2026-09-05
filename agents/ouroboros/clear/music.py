"""MusicAgent — ADK_AGENTS.md §2.2 table. Adds Entity Search (publishers/labels) when
the Task result leaves a rights-holder field null.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.ouroboros.clear.schemas import SpecialistOutput
from agents.ouroboros.clear.specialist import verify_batch
from agents.ouroboros.prompts.render import render
from agents.ouroboros.tools import ledger
from agents.ouroboros.tools.resilience import resilient_model
from packages.parallel_client.entity import search as entity_search


def _augment_music(claim_row: dict[str, object], content: dict[str, object]) -> dict[str, object]:
    missing_holder = not content.get("composition_rights_holder") or not content.get(
        "master_rights_holder"
    )
    if not missing_holder:
        return content
    entity_text = str(claim_row.get("entity_text", ""))
    hits = entity_search(
        f"music publisher, songwriter estate, or record label for the song '{entity_text}'",
        "companies",
        limit=5,
    )
    content["entity_search_candidates"] = [h.model_dump(mode="json") for h in hits]
    return content


async def verify_music_batch(
    claim_ids: list[str], *, project_id: str, studio_id: str, jurisdictions: list[str]
) -> dict[str, object]:
    """Verify a batch of music claims: composition/master rights holders, PRO,
    licensing contact, known sync restrictions."""
    return await verify_batch(
        claim_ids,
        spec_name="legal_music",
        project_id=project_id,
        studio_id=studio_id,
        jurisdictions=jurisdictions,
        augment=_augment_music,
    )


def _instruction(ctx: ReadonlyContext) -> str:
    return render(
        "specialist",
        agent_name="MusicAgent",
        category="music",
        objective_template=(
            "Identify composition and master rights holders, the relevant PRO for "
            "{jurisdictions}, official sync-licensing contact, and any known refusal "
            "to license for '{entity}'."
        ),
        tool_name="verify_music_batch",
        categories=["music"],
        project_id=ctx.state.get("project_id", ""),
        studio_id=ctx.state.get("studio_id", ""),
        jurisdictions=", ".join(ctx.state.get("jurisdictions", [])),
    )


music_agent = LlmAgent(
    name="MusicAgent",
    model=resilient_model("gemini-3.5-flash"),
    instruction=_instruction,
    tools=[ledger.list_claims, verify_music_batch],
    output_schema=SpecialistOutput,
    output_key="music_results",
)
