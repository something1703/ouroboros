#!/usr/bin/env python3
"""PHASE_09.md §9.1: runs `evals/golden/{legal,factual}.yaml` through the *real*
specialist code paths (`agents.ouroboros.clear.specialist.verify_batch`,
`agents.ouroboros.truecut.fact.verify_fact_batch` -- the exact same functions the
deployed CLEAR/TRUE CUT pipelines call, not a reimplementation), against real Parallel
API calls (core-fast, escalating to pro per each path's own real rules).

Computes field accuracy (legal), verdict accuracy (factual), citation presence,
confidence calibration (precision of `high`-confidence marks), cost, and latency.
Writes `evals/results/<date>.json` and prints a markdown table.

Needs a real local Postgres + Toolbox (`docker compose up -d postgres toolbox`,
`alembic upgrade head`) and a real `PARALLEL_API_KEY` (env var or Secret Manager) --
this makes real, budgeted Parallel API calls (a few dollars for the full 50-claim set
at this repo's current SKU prices, config/parallel.py::PRICE_TABLE_USD).

Usage: DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev \
       TOOLBOX_MCP_URL=http://localhost:5001 GOOGLE_CLOUD_PROJECT=ouroboros-507503 \
       uv run python evals/run_golden.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from agents.ouroboros.clear.specialist import verify_batch
from agents.ouroboros.truecut.fact import verify_fact_batch
from packages.claims.enums import ClaimCategory, ClaimKind, Confidence
from packages.claims.models import Asset, Claim, Project, SourceRef
from packages.ledger.db import session_scope
from packages.ledger.repositories import AssetRepo, ClaimRepo, EvidenceRepo, ProjectRepo

_GOLDEN_DIR = Path(__file__).parent / "golden"
_RESULTS_DIR = Path(__file__).parent / "results"

_LEGAL_PROJECT_ID = "eval-golden-legal"
_FACTUAL_PROJECT_ID = "eval-golden-factual"
_STUDIO_ID = "studio-eval-golden"

# ADK_AGENTS.md §2.2: `location` and `artwork` share one Task spec.
_SPEC_BY_CATEGORY = {
    "music": "legal_music",
    "brand": "legal_brand",
    "person": "legal_person",
    "location": "legal_location_artwork",
    "artwork": "legal_location_artwork",
}


@dataclass
class ClaimResult:
    claim_id: str
    golden_id: str
    correct: bool
    has_citation: bool
    confidence: str
    cost_usd: float
    error: str | None = None


@dataclass
class Metrics:
    domain: str
    total: int = 0
    correct: int = 0
    with_citation: int = 0
    high_confidence_total: int = 0
    high_confidence_correct: int = 0
    total_cost_usd: float = 0.0
    latency_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def citation_presence(self) -> float:
        return self.with_citation / self.total if self.total else 0.0

    @property
    def high_confidence_precision(self) -> float:
        return (
            self.high_confidence_correct / self.high_confidence_total
            if self.high_confidence_total
            else 0.0
        )


def _load_golden(name: str) -> list[dict[str, Any]]:
    with open(_GOLDEN_DIR / f"{name}.yaml") as f:
        cases: list[dict[str, Any]] = yaml.safe_load(f)
    return cases


def _legal_field_correct(expected: dict[str, Any], output: dict[str, Any]) -> bool:
    """Each golden legal case names exactly one expected field. Booleans/enum-like
    strings (is_living, is_public_domain, artwork_copyright_status) are checked
    exactly; free-text strings (rights holders, owners) as a case-insensitive
    substring match, since a Task's own real answer is prose, not a fixed token.

    `specialist.py::_verify_one_claim` has a real, deterministic fast path for a
    high-priority-number, obviously-public-domain claim: it skips the Task call
    entirely and writes `{"signal": "public_domain_or_no_rights_needed"}` instead of
    the full `legal_music.json`-shaped output -- a correct answer via a different
    (cheaper) real code path, not a schema mismatch to penalize."""
    if expected.get("is_public_domain") is True and output.get("signal") == (
        "public_domain_or_no_rights_needed"
    ):
        return True
    for key, expected_value in expected.items():
        actual = output.get(key)
        if isinstance(expected_value, bool):
            if actual != expected_value:
                return False
        elif key == "artwork_copyright_status":
            if str(actual).strip().lower() != str(expected_value).strip().lower():
                return False
        else:
            if str(expected_value).lower() not in str(actual or "").lower():
                return False
    return True


def _factual_verdict_correct(expected: dict[str, Any], output: dict[str, Any]) -> bool:
    return str(output.get("verdict", "")).strip().lower() == str(
        expected["verdict"]
    ).strip().lower().replace(" ", "_")


def _seed_legal_project() -> list[dict[str, Any]]:
    cases = _load_golden("legal")
    with session_scope() as session:
        ProjectRepo.upsert(
            session,
            Project(
                project_id=_LEGAL_PROJECT_ID,
                studio_id=_STUDIO_ID,
                title="Golden Set (Legal)",
                release_date=date(2027, 1, 1),
                shooting_countries=["us"],
                distribution_territories=["us", "gb", "in", "de", "jp"],
                budget_cap_usd=Decimal("10.00"),
                created_at=datetime.now(UTC),
            ),
        )
        AssetRepo.upsert(
            session,
            Asset(
                asset_id=f"{_LEGAL_PROJECT_ID}-asset",
                project_id=_LEGAL_PROJECT_ID,
                kind="script",
                gcs_uri="gs://local-dev/golden-legal.pdf",
                language="en",
                page_count=len(cases),
                ingested_at=datetime.now(UTC),
            ),
        )
        claims = []
        for i, case in enumerate(cases, start=1):
            source = SourceRef(
                asset_id=f"{_LEGAL_PROJECT_ID}-asset", page=i, excerpt=case["claim_text"]
            )
            claims.append(
                Claim.new(
                    project_id=_LEGAL_PROJECT_ID,
                    studio_id=_STUDIO_ID,
                    kind=ClaimKind.LEGAL,
                    category=ClaimCategory(case["category"]),
                    entity_text=case["entity_text"],
                    claim_text=case["claim_text"],
                    language=case["language"],
                    source=source,
                    jurisdictions=case["jurisdictions"],
                    priority=case["priority"],
                )
            )
        ClaimRepo.upsert_many(session, claims)
        for case, claim in zip(cases, claims, strict=True):
            case["_claim_id"] = claim.claim_id
    return cases


def _seed_factual_project() -> list[dict[str, Any]]:
    cases = _load_golden("factual")
    with session_scope() as session:
        ProjectRepo.upsert(
            session,
            Project(
                project_id=_FACTUAL_PROJECT_ID,
                studio_id=_STUDIO_ID,
                title="Golden Set (Factual)",
                release_date=date(2027, 1, 1),
                shooting_countries=["us"],
                distribution_territories=["us", "gb", "in", "de", "jp"],
                budget_cap_usd=Decimal("10.00"),
                created_at=datetime.now(UTC),
            ),
        )
        AssetRepo.upsert(
            session,
            Asset(
                asset_id=f"{_FACTUAL_PROJECT_ID}-asset",
                project_id=_FACTUAL_PROJECT_ID,
                kind="cut",
                gcs_uri="gs://local-dev/golden-factual.mp4",
                duration_ms=300_000,
                ingested_at=datetime.now(UTC),
            ),
        )
        claims = []
        for case in cases:
            source = SourceRef(
                asset_id=f"{_FACTUAL_PROJECT_ID}-asset",
                t_start_ms=case["t_start_ms"],
                t_end_ms=case["t_end_ms"],
                channel=case["channel"],
                excerpt=case["claim_text"],
            )
            claims.append(
                Claim.new(
                    project_id=_FACTUAL_PROJECT_ID,
                    studio_id=_STUDIO_ID,
                    kind=ClaimKind.FACTUAL,
                    category=ClaimCategory(case["category"]),
                    entity_text=case["entity_text"],
                    claim_text=case["claim_text"],
                    language=case["language"],
                    source=source,
                    jurisdictions=case["jurisdictions"],
                    priority=case["priority"],
                )
            )
        ClaimRepo.upsert_many(session, claims)
        for case, claim in zip(cases, claims, strict=True):
            case["_claim_id"] = claim.claim_id
    return cases


def _collect_results(
    cases: list[dict[str, Any]],
    *,
    domain: str,
    is_correct: Any,
    batch_seconds: float,
    errors_by_claim: dict[str, str],
) -> Metrics:
    metrics = Metrics(domain=domain)
    with session_scope() as session:
        for case in cases:
            claim_id = case["_claim_id"]
            metrics.total += 1
            if claim_id in errors_by_claim:
                metrics.errors.append(f"{case['id']}: {errors_by_claim[claim_id]}")
                continue

            evidence = EvidenceRepo.latest_for_claim(session, claim_id)
            if evidence is None:
                metrics.errors.append(f"{case['id']}: no evidence written")
                continue

            correct = is_correct(case["expected"], evidence.output)
            has_citation = any(basis.citations for basis in evidence.basis)
            metrics.correct += int(correct)
            metrics.with_citation += int(has_citation)
            metrics.total_cost_usd += float(evidence.cost_usd)
            if evidence.overall_confidence == Confidence.HIGH:
                metrics.high_confidence_total += 1
                metrics.high_confidence_correct += int(correct)

    metrics.latency_seconds = batch_seconds / len(cases) if cases else 0.0
    return metrics


async def _run_legal() -> Metrics:
    """Each golden case names its own jurisdictions (PHASE_09.md §9.1's "mix
    jurisdictions"), but `verify_batch` takes one shared jurisdictions list per call --
    so each claim gets its own singleton `verify_batch` call (still the exact same
    per-claim algorithm, `_verify_one_claim`, as a real multi-claim batch would run),
    all gathered together for real concurrency instead of one at a time."""
    cases = _seed_legal_project()
    errors_by_claim: dict[str, str] = {}

    async def _one(case: dict[str, Any]) -> None:
        result = await verify_batch(
            [case["_claim_id"]],
            spec_name=_SPEC_BY_CATEGORY[case["category"]],
            project_id=_LEGAL_PROJECT_ID,
            studio_id=_STUDIO_ID,
            jurisdictions=case["jurisdictions"],
        )
        errors: list[dict[str, str]] = result["errors"]  # type: ignore[assignment]
        for err in errors:
            errors_by_claim[err["claim_id"]] = err["error"]

    start = time.monotonic()
    await asyncio.gather(*(_one(case) for case in cases))
    total_seconds = time.monotonic() - start

    return _collect_results(
        cases,
        domain="legal",
        is_correct=_legal_field_correct,
        batch_seconds=total_seconds,
        errors_by_claim=errors_by_claim,
    )


async def _run_factual() -> Metrics:
    """Same one-claim-per-call reasoning as `_run_legal` -- `verify_fact_batch` also
    takes one shared jurisdictions list per call, and the golden set's whole point is
    varying jurisdictions per claim."""
    cases = _seed_factual_project()
    errors_by_claim: dict[str, str] = {}

    async def _one(case: dict[str, Any]) -> None:
        result = await verify_fact_batch(
            [case["_claim_id"]],
            project_id=_FACTUAL_PROJECT_ID,
            studio_id=_STUDIO_ID,
            jurisdictions=case["jurisdictions"],
        )
        errors: list[dict[str, str]] = result["errors"]  # type: ignore[assignment]
        for err in errors:
            errors_by_claim[err["claim_id"]] = err["error"]

    start = time.monotonic()
    await asyncio.gather(*(_one(case) for case in cases))
    total_seconds = time.monotonic() - start

    return _collect_results(
        cases,
        domain="factual",
        is_correct=_factual_verdict_correct,
        batch_seconds=total_seconds,
        errors_by_claim=errors_by_claim,
    )


def _print_table(legal: Metrics, factual: Metrics) -> str:
    lines = [
        "| Metric | Legal | Factual |",
        "|---|---|---|",
        f"| Field/verdict accuracy | {legal.accuracy:.0%} | {factual.accuracy:.0%} |",
        f"| Citation presence | {legal.citation_presence:.0%} | {factual.citation_presence:.0%} |",
        f"| High-confidence precision | {legal.high_confidence_precision:.0%} "
        f"({legal.high_confidence_total} high) | {factual.high_confidence_precision:.0%} "
        f"({factual.high_confidence_total} high) |",
        f"| Total cost | ${legal.total_cost_usd:.3f} | ${factual.total_cost_usd:.3f} |",
        f"| Avg latency/claim | {legal.latency_seconds:.1f}s | {factual.latency_seconds:.1f}s |",
        f"| Errors | {len(legal.errors)} | {len(factual.errors)} |",
    ]
    table = "\n".join(lines)
    print(table)
    return table


def main() -> int:
    # Found live: the first batch's claims all fire asyncio.to_thread simultaneously,
    # racing to populate get_secret's lru_cache for PARALLEL_API_KEY -- concurrent
    # cold-cache Secret Manager calls sometimes errored (surfaced, confusingly, as
    # "secret not found" -- packages/common/secrets.py maps every GoogleAPICallError
    # to NotFound). Priming it once, synchronously, before any concurrent work starts
    # avoids the stampede entirely.
    from packages.common.secrets import get_secret

    get_secret("PARALLEL_API_KEY")

    legal_metrics = asyncio.run(_run_legal())
    factual_metrics = asyncio.run(_run_factual())

    table = _print_table(legal_metrics, factual_metrics)

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_path = _RESULTS_DIR / f"{date.today().isoformat()}.json"
    with open(result_path, "w") as f:
        json.dump(
            {
                "date": date.today().isoformat(),
                "legal": {
                    "total": legal_metrics.total,
                    "accuracy": legal_metrics.accuracy,
                    "citation_presence": legal_metrics.citation_presence,
                    "high_confidence_precision": legal_metrics.high_confidence_precision,
                    "high_confidence_total": legal_metrics.high_confidence_total,
                    "total_cost_usd": legal_metrics.total_cost_usd,
                    "avg_latency_seconds": legal_metrics.latency_seconds,
                    "errors": legal_metrics.errors,
                },
                "factual": {
                    "total": factual_metrics.total,
                    "accuracy": factual_metrics.accuracy,
                    "citation_presence": factual_metrics.citation_presence,
                    "high_confidence_precision": factual_metrics.high_confidence_precision,
                    "high_confidence_total": factual_metrics.high_confidence_total,
                    "total_cost_usd": factual_metrics.total_cost_usd,
                    "avg_latency_seconds": factual_metrics.latency_seconds,
                    "errors": factual_metrics.errors,
                },
                "table_markdown": table,
            },
            f,
            indent=2,
        )
    print(f"\nWrote {result_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
