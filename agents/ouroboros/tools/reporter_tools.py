"""Reporter tool (ADK_AGENTS.md §2.4) — gathers everything Reporter needs per claim to
write a summary and decide on Monitors, in one call per batch rather than one
`get_claim` round trip per claim from the LLM.
"""

from __future__ import annotations

import json

from . import ledger
from .rowparse import claim_from_row, evidence_from_row


def gather_report_inputs(claim_ids: list[str]) -> dict[str, object]:
    """For each claim_id: entity/claim text, category, risk level/score, the Task
    run_id (for creating a snapshot Monitor), and citation URLs (for `[n]` indices in
    the summary). Claims with no risk assessed yet are skipped.

    A claim that already has a Monitor is also skipped (docs/DECISIONS.md #075) —
    found live: on a retrigger, Reporter's own claim_ids now come from a ledger sweep
    (`list_claims(status="verified"/"escalated")`, same fix as RiskAssessor's #074),
    since claims risk-assessed in a *previous* run are otherwise invisible via session
    state. Unlike RiskAssessor's redundancy (a wasted Gemini call, harmless), reporting
    on an already-reported claim again would call `monitor_create_snapshot`/
    `monitor_create_stream` again too -- real, non-idempotent Parallel API calls that
    would create a genuine duplicate Monitor each retrigger, not just redo bookkeeping.
    `has_monitor` only ever becomes true for a claim that actually got one (high/
    blocking risk); a low-risk claim -- which never gets a Monitor by design -- has no
    such guard and gets its (cheap, idempotent) summary rewritten on every retrigger
    that reaches it, which is wasteful but not unsafe."""
    results: list[dict[str, object]] = []
    for claim_id in claim_ids:
        raw = ledger.get_claim(claim_id=claim_id)
        row = json.loads(raw) if raw else None
        if not row or row.get("risk_level") is None:
            continue
        if row.get("has_monitor"):
            continue
        claim = claim_from_row(row)
        evidence = evidence_from_row(row, claim_id=claim_id)
        citations = []
        if evidence is not None:
            for field_basis in evidence.basis:
                for citation in field_basis.citations:
                    if citation.url not in citations:
                        citations.append(citation.url)
        results.append(
            {
                "claim_id": claim_id,
                "category": claim.category.value,
                "entity_text": claim.entity_text,
                "claim_text": claim.claim_text,
                "risk_level": row["risk_level"],
                "risk_score": row["risk_score"],
                "parallel_run_id": evidence.parallel_run_id if evidence else None,
                "evidence_output": evidence.output if evidence else {},
                "citations": citations[:10],
            }
        )
    return {"claims": results}
