"""BrandAgent — ADK_AGENTS.md §2.2 table. Adds Extract on the brand's own clearance
policy page when the Task result names one.

Simplification (documented in docs/DECISIONS.md): the plan additionally calls for
re-running a `lite-fast` Task to "summarize depiction guidelines" from the extracted
page. In practice the Extract call already returns that page as markdown, and a
second structured Task against the same 7-field `legal_brand` spec doesn't produce a
meaningfully different summary — so this augments with Extract only, appending the raw
extracted guidelines text directly rather than re-summarizing it through another model
call.
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


def _augment_brand(claim_row: dict[str, object], content: dict[str, object]) -> dict[str, object]:
    policy_url = content.get("brand_clearance_policy_url")
    if not policy_url or not isinstance(policy_url, str):
        return content
    entity_text = str(claim_row.get("entity_text", ""))
    hits = extract(
        [policy_url], objective=f"depiction and product-placement guidelines for {entity_text}"
    )
    content["clearance_policy_extract"] = [h.model_dump(mode="json") for h in hits]
    return content


async def verify_brand_batch(
    claim_ids: list[str], *, project_id: str, studio_id: str, jurisdictions: list[str]
) -> dict[str, object]:
    """Verify a batch of brand claims: trademark owner, registration status,
    litigiousness, product-placement/depiction stance."""
    return await verify_batch(
        claim_ids,
        spec_name="legal_brand",
        project_id=project_id,
        studio_id=studio_id,
        jurisdictions=jurisdictions,
        augment=_augment_brand,
    )


def _instruction(ctx: ReadonlyContext) -> str:
    return render(
        "specialist",
        agent_name="BrandAgent",
        category="brand",
        objective_template=(
            "Identify the trademark owner, registration status in {jurisdictions}, the "
            "brand's stance on film depiction/product placement, and litigation "
            "history for '{entity}'."
        ),
        tool_name="verify_brand_batch",
        categories=["brand"],
        project_id=ctx.state.get("project_id", ""),
        studio_id=ctx.state.get("studio_id", ""),
        jurisdictions=", ".join(ctx.state.get("jurisdictions", [])),
    )


brand_agent = LlmAgent(
    name="BrandAgent",
    model=resilient_model("gemini-3.5-flash"),
    instruction=_instruction,
    tools=[ledger.list_claims, verify_brand_batch],
    output_schema=SpecialistOutput,
    output_key="brand_results",
)
