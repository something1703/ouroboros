"""LocationArtAgent — ADK_AGENTS.md §2.2 table. Adds Extract on the filming permit
authority page when the Task result names one. Handles both `location` and `artwork`
claim categories (ClaimTriage merges them into one `location_artwork` batch), using the
`legal_location_artwork` spec for both.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.ouroboros.clear.schemas import SpecialistOutput
from agents.ouroboros.clear.specialist import verify_batch
from agents.ouroboros.prompts.render import render
from agents.ouroboros.tools import ledger
from agents.ouroboros.tools.resilience import resilient_model
from packages.parallel_client.extract import extract


def _augment_location_art(
    claim_row: dict[str, object], content: dict[str, object]
) -> dict[str, object]:
    permit_url = content.get("permit_authority_url")
    if not permit_url or not isinstance(permit_url, str):
        return content
    entity_text = str(claim_row.get("entity_text", ""))
    hits = extract([permit_url], objective=f"filming/photography permit process for {entity_text}")
    content["permit_page_extract"] = [h.model_dump(mode="json") for h in hits]
    return content


async def verify_location_artwork_batch(
    claim_ids: list[str], *, project_id: str, studio_id: str, jurisdictions: list[str]
) -> dict[str, object]:
    """Verify a batch of location and artwork claims: owner/custodian, filming permit
    requirements, artwork copyright status."""
    # ClaimTriage merges 'location' and 'artwork' claims into one batch; verify_batch
    # reads each claim's own `category` field from the ledger to pick the right
    # build_objective() template — only the spec (shared between the two) is fixed here.
    return await verify_batch(
        claim_ids,
        spec_name="legal_location_artwork",
        project_id=project_id,
        studio_id=studio_id,
        jurisdictions=jurisdictions,
        augment=_augment_location_art,
    )


def _instruction(ctx: ReadonlyContext) -> str:
    return render(
        "specialist",
        agent_name="LocationArtAgent",
        category="location_artwork",
        objective_template=(
            "Determine ownership/custodian, filming-permit requirements and authority, "
            "and copyright status of any artwork for '{entity}' in {jurisdictions}."
        ),
        tool_name="verify_location_artwork_batch",
        categories=["location", "artwork"],
        project_id=ctx.state.get("project_id", ""),
        studio_id=ctx.state.get("studio_id", ""),
        jurisdictions=", ".join(ctx.state.get("jurisdictions", [])),
    )


location_art_agent = LlmAgent(
    name="LocationArtAgent",
    model=resilient_model("gemini-3.5-flash"),
    instruction=_instruction,
    tools=[ledger.list_claims, verify_location_artwork_batch],
    output_schema=SpecialistOutput,
    output_key="location_artwork_results",
)
