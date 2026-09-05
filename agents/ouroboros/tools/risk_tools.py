"""Risk tool (ADK_AGENTS.md §2.3) — runs the deterministic pre-score
(packages/claims/risk.prescore) for a batch of claims so RiskAssessor can read it and
decide whether to adjust ±1 level with its own rationale."""

from __future__ import annotations

import json

from packages.claims.risk import prescore

from . import ledger
from .rowparse import claim_from_row, evidence_from_row


def gather_risk_inputs(claim_ids: list[str]) -> dict[str, object]:
    """For each claim_id, fetch the claim + its latest Evidence and run the
    deterministic pre-score. Returns one entry per claim with everything RiskAssessor
    needs to decide whether to adjust the level ±1: the pre-scored level/score/
    rationale, the raw evidence output (including any `territory_notes` field), and
    the claim's kind/category/priority/jurisdictions (`kind` decides which rubric in
    `risk_assessor.md` applies). Claims with no evidence yet are
    skipped (not included in the result) — that shouldn't happen for a claim already
    in a `*_results.verified`/`escalated` list, but a specialist error could leave one
    behind.

    Claims that already have a risk assessment are also skipped (docs/DECISIONS.md
    #074): RiskAssessor's own claim_ids now come from a ledger sweep
    (`list_claims(status="verified"/"escalated")`), not session state, specifically so
    a retriggered run can pick up claims a *previous* run's specialists verified but
    never got risk-assessed. Without this check, every retrigger would re-assess every
    already-assessed claim too -- a real Gemini call per claim for no new information,
    eating into the next 10-minute `stream_query` window (docs/DECISIONS.md #072)
    before Reporter ever runs. Re-verification producing genuinely new evidence for an
    already-assessed claim is a real gap this leaves open, but is out of scope for the
    initial CLEAR pass (PHASE_05.md) this sweep exists for."""
    results: list[dict[str, object]] = []
    for claim_id in claim_ids:
        raw = ledger.get_claim(claim_id=claim_id)
        row = json.loads(raw) if raw else None
        if not row:
            continue
        if row.get("risk_level") is not None:
            continue
        evidence = evidence_from_row(row, claim_id=claim_id)
        if evidence is None:
            continue
        claim = claim_from_row(row)
        level, score, rationale = prescore(evidence, claim)
        results.append(
            {
                "claim_id": claim_id,
                "evidence_id": evidence.evidence_id,
                "kind": claim.kind.value,
                "category": claim.category.value,
                "priority": claim.priority,
                "jurisdictions": claim.jurisdictions,
                "prescore_level": level.value,
                "prescore_score": score,
                "prescore_rationale": rationale,
                "evidence_output": evidence.output,
            }
        )
    return {"claims": results}
