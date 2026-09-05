"""Parses a Parallel `FieldBasis[]` into our own `packages.claims.FieldBasis[]`, and
computes `overall_confidence` — the min-rule over the *spec's own* required fields
(PARALLEL_INTEGRATION.md §4.2), not a Parallel concept itself.
"""

from __future__ import annotations

from datetime import UTC, datetime

import parallel.types as parallel_types

from packages.claims.enums import CONFIDENCE_ORDER, Confidence
from packages.claims.models import Citation, FieldBasis

_CONFIDENCE_MAP: dict[str | None, Confidence] = {
    "high": Confidence.HIGH,
    "medium": Confidence.MEDIUM,
    "low": Confidence.LOW,
    None: Confidence.UNKNOWN,
}


def _map_confidence(value: str | None) -> Confidence:
    return _CONFIDENCE_MAP.get(value, Confidence.UNKNOWN)


def parse_basis(raw_basis: list[parallel_types.FieldBasis]) -> list[FieldBasis]:
    now = datetime.now(UTC)
    parsed: list[FieldBasis] = []
    for item in raw_basis:
        citations = [
            Citation(
                url=c.url,
                excerpt=c.excerpts[0] if c.excerpts else None,
                retrieved_at=now,
            )
            for c in (item.citations or [])
        ]
        parsed.append(
            FieldBasis(
                field=item.field,
                citations=citations,
                reasoning=item.reasoning,
                confidence=_map_confidence(item.confidence),
            )
        )
    return parsed


def overall_confidence(basis: list[FieldBasis], *, required_fields: list[str]) -> Confidence:
    """min(confidence) over exactly the spec's `required_fields` — a field missing from
    `basis` entirely (Parallel didn't return a FieldBasis entry for it) counts as
    `unknown`, same as an explicit null confidence."""
    by_field = {b.field: b.confidence for b in basis}
    worst = Confidence.HIGH
    for field in required_fields:
        confidence = by_field.get(field, Confidence.UNKNOWN)
        if CONFIDENCE_ORDER.index(confidence) < CONFIDENCE_ORDER.index(worst):
            worst = confidence
    return worst
