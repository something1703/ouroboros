"""PersonAgent — ADK_AGENTS.md §2.2 table. Adds Entity Search (estates, agents) when
the Task result leaves `estate_or_representation` null.
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


def _augment_person(claim_row: dict[str, object], content: dict[str, object]) -> dict[str, object]:
    if content.get("estate_or_representation"):
        return content
    entity_text = str(claim_row.get("entity_text", ""))
    hits = entity_search(
        f"talent agency, estate, or legal representative for '{entity_text}'",
        "people",
        limit=5,
    )
    content["entity_search_candidates"] = [h.model_dump(mode="json") for h in hits]
    return content


async def verify_person_batch(
    claim_ids: list[str], *, project_id: str, studio_id: str, jurisdictions: list[str]
) -> dict[str, object]:
    """Verify a batch of person claims: living/public-figure status, representation,
    right-of-publicity, litigation history over depiction."""
    return await verify_batch(
        claim_ids,
        spec_name="legal_person",
        project_id=project_id,
        studio_id=studio_id,
        jurisdictions=jurisdictions,
        augment=_augment_person,
    )


def _instruction(ctx: ReadonlyContext) -> str:
    return render(
        "specialist",
        agent_name="PersonAgent",
        category="person",
        objective_template=(
            "Determine whether '{entity}' is living, a public figure, who represents "
            "them or their estate, and right-of-publicity rules in {jurisdictions}."
        ),
        tool_name="verify_person_batch",
        categories=["person"],
        project_id=ctx.state.get("project_id", ""),
        studio_id=ctx.state.get("studio_id", ""),
        jurisdictions=", ".join(ctx.state.get("jurisdictions", [])),
    )


person_agent = LlmAgent(
    name="PersonAgent",
    model=resilient_model("gemini-3.5-flash"),
    instruction=_instruction,
    tools=[ledger.list_claims, verify_person_batch],
    output_schema=SpecialistOutput,
    output_key="person_results",
)
