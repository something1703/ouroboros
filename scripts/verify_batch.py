#!/usr/bin/env python3
"""Batch-verify every pending claim in a project (optionally filtered by category),
concurrently. See PHASE_04.md §4.6.

Usage: uv run python scripts/verify_batch.py --project demo [--category music] [--concurrency 5] [--dry-run]
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

from packages.claims.enums import ClaimCategory, VerificationStatus
from packages.ledger.db import session_scope
from packages.ledger.repositories import ClaimRepo, ProjectRepo
from scripts.verify_claim import verify_claim


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--category", choices=[c.value for c in ClaimCategory], default=None)
    parser.add_argument("--processor", default="core-fast")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with session_scope() as session:
        before_spend = ProjectRepo.spend(session, args.project)
        claims = ClaimRepo.list_by_project(
            session,
            args.project,
            status=VerificationStatus.PENDING,
            category=args.category,
            limit=500,
        )

    if not claims:
        print(f"no pending claims for project={args.project!r} category={args.category!r}")
        return 0

    print(f"verifying {len(claims)} claims (concurrency={args.concurrency})...")

    errors: list[tuple[str, str]] = []
    verified = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(
                verify_claim,
                claim.claim_id,
                processor=args.processor,
                escalate_flag=True,
                dry_run=args.dry_run,
            ): claim.claim_id
            for claim in claims
        }
        for future in as_completed(futures):
            claim_id = futures[future]
            try:
                future.result()
                verified += 1
            except Exception as exc:
                errors.append((claim_id, str(exc)))

    with session_scope() as session:
        after_spend = ProjectRepo.spend(session, args.project)

    print(f"\nverified: {verified}/{len(claims)}")
    if errors:
        print(f"errors: {len(errors)}")
        for claim_id, error in errors:
            print(f"  {claim_id}: {error}")
    spend_delta = after_spend - before_spend if not args.dry_run else Decimal("0")
    print(f"spend this run: ${spend_delta:.4f} (project total now: ${after_spend:.4f})")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
