from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from packages.claims.drift import ClaimDriftInput, reality_drift
from packages.claims.enums import RiskLevel

_NOW = datetime(2026, 9, 3, tzinfo=UTC)

_risk_levels = st.sampled_from(list(RiskLevel))
_claim_inputs = st.builds(
    ClaimDriftInput,
    claim_id=st.text(min_size=1, max_size=10),
    risk_level=_risk_levels,
    changed=st.booleans(),
    latest_cycle_at=st.datetimes(
        min_value=datetime(2026, 1, 1), max_value=datetime(2026, 9, 3), timezones=st.just(UTC)
    ),
)


@given(claims=st.lists(_claim_inputs, max_size=30))
def test_drift_is_always_in_unit_interval(claims: list[ClaimDriftInput]) -> None:
    result = reality_drift(claims, now=_NOW)
    assert 0.0 <= result.drift <= 1.0
    assert 0.0 <= result.drift_7d <= 1.0


def test_no_claims_means_zero_drift() -> None:
    result = reality_drift([], now=_NOW)
    assert result.drift == 0.0
    assert result.drift_7d == 0.0
    assert result.last_change_at is None
    assert result.total_count == 0


def test_all_changed_means_drift_of_one() -> None:
    claims = [
        ClaimDriftInput(
            claim_id="a", risk_level=RiskLevel.HIGH, changed=True, latest_cycle_at=_NOW
        ),
        ClaimDriftInput(claim_id="b", risk_level=RiskLevel.LOW, changed=True, latest_cycle_at=_NOW),
    ]
    result = reality_drift(claims, now=_NOW)
    assert result.drift == 1.0
    assert result.changed_count == 2


def test_none_changed_means_drift_of_zero() -> None:
    claims = [
        ClaimDriftInput(
            claim_id="a", risk_level=RiskLevel.HIGH, changed=False, latest_cycle_at=_NOW
        ),
    ]
    result = reality_drift(claims, now=_NOW)
    assert result.drift == 0.0


def test_drift_7d_excludes_old_cycles() -> None:
    old = ClaimDriftInput(
        claim_id="old",
        risk_level=RiskLevel.HIGH,
        changed=True,
        latest_cycle_at=_NOW - timedelta(days=30),
    )
    recent = ClaimDriftInput(
        claim_id="recent", risk_level=RiskLevel.HIGH, changed=True, latest_cycle_at=_NOW
    )
    result = reality_drift([old, recent], now=_NOW)
    assert result.drift == 1.0  # both changed, full window
    assert result.drift_7d == 1.0  # only `recent` is in the 7d window, and it changed


def test_last_change_at_is_latest_among_changed() -> None:
    earlier = ClaimDriftInput(
        claim_id="a",
        risk_level=RiskLevel.LOW,
        changed=True,
        latest_cycle_at=_NOW - timedelta(days=1),
    )
    later = ClaimDriftInput(
        claim_id="b", risk_level=RiskLevel.LOW, changed=True, latest_cycle_at=_NOW
    )
    unchanged = ClaimDriftInput(
        claim_id="c", risk_level=RiskLevel.LOW, changed=False, latest_cycle_at=_NOW
    )
    result = reality_drift([earlier, later, unchanged], now=_NOW)
    assert result.last_change_at == _NOW
