"""Reality Drift: how much of the project's risk picture has changed lately. See DATA_MODEL.md §6.

    drift = Σ_i w_i · changed_i / Σ_i w_i
    where i ranges over claims with ≥1 evidence,
          w_i = {none:0.2, low:0.4, medium:0.7, high:1.0, blocking:1.2}[risk_level_i]
          changed_i = 1 if the latest cycle differs from the previous cycle, else 0

This package has no DB access — the caller (reverify_worker, Phase 7.2) does the actual
per-claim diff (verdict/holder/confidence/risk_level between cycle n and n-1) and passes
the result in as `ClaimDriftInput`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel

from packages.claims.enums import RiskLevel

_RISK_WEIGHTS: dict[RiskLevel, float] = {
    RiskLevel.NONE: 0.2,
    RiskLevel.LOW: 0.4,
    RiskLevel.MEDIUM: 0.7,
    RiskLevel.HIGH: 1.0,
    RiskLevel.BLOCKING: 1.2,
}

_DRIFT_7D_WINDOW = timedelta(days=7)


class ClaimDriftInput(BaseModel):
    """One claim's contribution to drift: its current risk level and whether its latest
    verification cycle changed anything versus the previous cycle."""

    claim_id: str
    risk_level: RiskLevel
    changed: bool
    latest_cycle_at: datetime


class DriftResult(BaseModel):
    drift: float
    drift_7d: float
    changed_count: int
    total_count: int
    last_change_at: datetime | None


def _weighted_drift(claims: list[ClaimDriftInput]) -> float:
    if not claims:
        return 0.0
    weight_sum = sum(_RISK_WEIGHTS[c.risk_level] for c in claims)
    if weight_sum == 0.0:
        return 0.0
    changed_sum = sum(_RISK_WEIGHTS[c.risk_level] for c in claims if c.changed)
    return changed_sum / weight_sum


def reality_drift(claims: list[ClaimDriftInput], *, now: datetime | None = None) -> DriftResult:
    """`claims` must include every claim with >=1 evidence cycle, changed or not —
    the unweighted-changed claims are what keeps the denominator honest."""
    now = now or datetime.now(UTC)

    drift = _weighted_drift(claims)

    recent = [c for c in claims if now - c.latest_cycle_at <= _DRIFT_7D_WINDOW]
    drift_7d = _weighted_drift(recent)

    changed_at = [c.latest_cycle_at for c in claims if c.changed]
    last_change_at = max(changed_at) if changed_at else None

    return DriftResult(
        drift=drift,
        drift_7d=drift_7d,
        changed_count=sum(1 for c in claims if c.changed),
        total_count=len(claims),
        last_change_at=last_change_at,
    )
