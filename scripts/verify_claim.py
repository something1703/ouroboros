#!/usr/bin/env python3
"""Verify a single claim end-to-end: search -> task -> basis -> prescore. Prints a
table; writes Evidence/Risk/VerificationEvent to the ledger unless --dry-run.
See PHASE_04.md §4.6.

Usage: uv run python scripts/verify_claim.py --claim-id X [--processor core-fast] [--escalate] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from config.parallel import SEARCH_MODE_DEFAULT
from packages.claims.enums import ClaimCategory, VerificationStatus
from packages.claims.models import Evidence, Risk, VerificationEvent
from packages.claims.risk import prescore
from packages.ledger.db import session_scope
from packages.ledger.repositories import (
    ClaimRepo,
    EvidenceRepo,
    RiskRepo,
    record_evidence_and_status,
)
from packages.parallel_client.cost import CostMeter
from packages.parallel_client.search import build_objective, search
from packages.parallel_client.task import TaskResult, build_input, run, should_escalate

# Category -> Task spec. Legal categories without a dedicated spec (quote) fall back to
# the closest rights-holder-shaped one; every factual category shares factual_claim
# (DATA_MODEL.md §2 only defines 4 legal + 1 factual spec).
_CATEGORY_SPEC: dict[ClaimCategory, str] = {
    ClaimCategory.MUSIC: "legal_music",
    ClaimCategory.BRAND: "legal_brand",
    ClaimCategory.PERSON: "legal_person",
    ClaimCategory.LOCATION: "legal_location_artwork",
    ClaimCategory.ARTWORK: "legal_location_artwork",
    ClaimCategory.QUOTE: "legal_location_artwork",
    ClaimCategory.EVENT: "factual_claim",
    ClaimCategory.STATISTIC: "factual_claim",
    ClaimCategory.ATTRIBUTION: "factual_claim",
    ClaimCategory.ARCHIVAL: "factual_claim",
    ClaimCategory.IDENTITY: "factual_claim",
}


def verify_claim(
    claim_id: str, *, processor: str, escalate_flag: bool, dry_run: bool
) -> TaskResult:
    with session_scope() as session:
        claim = ClaimRepo.require(session, claim_id)
        cycle = EvidenceRepo.next_cycle(session, claim_id)

    print(
        f"claim {claim_id}: {claim.entity_text!r} ({claim.category.value}, priority {claim.priority})"
    )

    objective, queries = build_objective(claim.category, claim.entity_text, claim.jurisdictions)
    with (
        session_scope() as cost_session,
        CostMeter(
            cost_session,
            claim.project_id,
            api="search",
            sku=f"search.{SEARCH_MODE_DEFAULT}",
            claim_id=claim_id,
        ),
    ):
        search_result = search(
            objective,
            queries,
            category=claim.category,
            location=claim.jurisdictions[0] if claim.jurisdictions else None,
            claim_id=claim_id,
        )
    top_urls = [hit.url for hit in search_result.hits[:5]]
    print(
        f"  search: {len(search_result.hits)} hits, top url: {top_urls[0] if top_urls else 'none'}"
    )

    task_input = build_input(
        claim.claim_text,
        jurisdictions=claim.jurisdictions,
        excerpt=claim.source.excerpt,
        top_urls=top_urls,
    )
    spec = _CATEGORY_SPEC[claim.category]
    with (
        session_scope() as cost_session,
        CostMeter(
            cost_session, claim.project_id, api="task", sku=f"task.{processor}", claim_id=claim_id
        ),
    ):
        result = run(
            task_input,
            spec,
            claim_id=claim_id,
            project_id=claim.project_id,
            cycle=cycle,
            processor=processor,
        )
    assert isinstance(result, TaskResult)
    print(
        f"  task: run_id={result.run_id}, processor={processor}, confidence={result.overall_confidence.value}"
    )

    if escalate_flag and should_escalate(result.overall_confidence, claim.priority):
        print("  escalating to processor=pro (low confidence, priority <= 2)...")
        with (
            session_scope() as cost_session,
            CostMeter(
                cost_session, claim.project_id, api="task", sku="task.pro", claim_id=claim_id
            ),
        ):
            escalated = run(
                task_input,
                spec,
                claim_id=claim_id,
                project_id=claim.project_id,
                cycle=cycle,
                processor="pro",
            )
        assert isinstance(escalated, TaskResult)
        result = escalated
        print(f"  escalated: confidence={result.overall_confidence.value}")

    now = datetime.now(UTC)
    evidence = Evidence(
        claim_id=claim_id,
        cycle=cycle,
        method="task",
        parallel_run_id=result.run_id,
        processor=result.processor,
        output=result.content if isinstance(result.content, dict) else {"text": result.content},
        basis=result.basis,
        overall_confidence=result.overall_confidence,
        created_at=now,
    )
    level, score, rationale = prescore(evidence, claim)
    print(f"  risk: {level.value} (score={score:.2f}) — {'; '.join(rationale)}")

    if dry_run:
        print("  --dry-run: not writing to the ledger")
        return result

    risk = Risk(
        claim_id=claim_id,
        evidence_id=evidence.evidence_id,
        level=level,
        score=score,
        rationale="; ".join(rationale),
        assessed_at=now,
    )
    event = VerificationEvent(
        claim_id=claim_id,
        at=now,
        actor="human",
        from_status=claim.status,
        to_status=VerificationStatus.VERIFIED,
        note=f"verify_claim.py: {spec} via {result.processor}",
        ref={"run_id": result.run_id},
    )
    with session_scope() as session:
        record_evidence_and_status(
            session, evidence=evidence, event=event, new_status=VerificationStatus.VERIFIED
        )
        RiskRepo.upsert(session, risk)
    print(f"  wrote evidence {evidence.evidence_id}, risk {level.value}, status -> verified")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim-id", required=True)
    parser.add_argument("--processor", default="core-fast")
    parser.add_argument("--escalate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        verify_claim(
            args.claim_id,
            processor=args.processor,
            escalate_flag=args.escalate,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
