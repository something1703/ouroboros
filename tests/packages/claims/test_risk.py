from datetime import UTC, datetime

import pytest

from packages.claims.enums import ClaimCategory, ClaimKind, Confidence, RiskLevel
from packages.claims.models import Claim, Evidence, SourceRef
from packages.claims.risk import prescore

_NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _claim(category: ClaimCategory, kind: ClaimKind, priority: int = 3) -> Claim:
    source = SourceRef(asset_id="asset-1", page=1, excerpt="excerpt")
    return Claim.new(
        project_id="demo",
        studio_id="studio-1",
        kind=kind,
        category=category,
        entity_text="Entity",
        claim_text="claim text",
        language="en",
        source=source,
        jurisdictions=["us"],
        priority=priority,
    )


def _evidence(output: dict[str, object], confidence: Confidence) -> Evidence:
    return Evidence(
        claim_id="x",
        cycle=1,
        method="task",
        output=output,
        basis=[],
        overall_confidence=confidence,
        created_at=_NOW,
    )


@pytest.mark.parametrize(
    "output",
    [
        {"is_living": True, "consent_recommended": True},
    ],
)
def test_living_person_no_consent_is_blocking(output: dict[str, object]) -> None:
    claim = _claim(ClaimCategory.PERSON, ClaimKind.LEGAL, priority=1)
    level, score, rationale = prescore(_evidence(output, Confidence.HIGH), claim)
    assert level == RiskLevel.BLOCKING
    assert score == 1.0
    assert rationale


def test_high_litigiousness_brand_is_blocking() -> None:
    claim = _claim(ClaimCategory.BRAND, ClaimKind.LEGAL)
    evidence = _evidence({"known_litigiousness": "high"}, Confidence.HIGH)
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.BLOCKING


def test_music_refusal_is_blocking() -> None:
    claim = _claim(ClaimCategory.MUSIC, ClaimKind.LEGAL)
    evidence = _evidence(
        {"known_sync_restrictions": "The estate has declined all sync licensing requests."},
        Confidence.MEDIUM,
    )
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.BLOCKING


def test_low_confidence_high_priority_is_high() -> None:
    claim = _claim(ClaimCategory.MUSIC, ClaimKind.LEGAL, priority=1)
    evidence = _evidence({}, Confidence.LOW)
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.HIGH


def test_expensive_cost_band_is_high() -> None:
    claim = _claim(ClaimCategory.MUSIC, ClaimKind.LEGAL, priority=5)
    evidence = _evidence({"typical_sync_cost_band": "10k-100k"}, Confidence.HIGH)
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.HIGH


def test_medium_confidence_is_medium() -> None:
    claim = _claim(ClaimCategory.LOCATION, ClaimKind.LEGAL, priority=5)
    evidence = _evidence({}, Confidence.MEDIUM)
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.MEDIUM


def test_public_domain_is_low() -> None:
    claim = _claim(ClaimCategory.MUSIC, ClaimKind.LEGAL, priority=5)
    evidence = _evidence({"is_public_domain": True}, Confidence.MEDIUM)
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.LOW


def test_high_confidence_generic_is_low() -> None:
    claim = _claim(ClaimCategory.ARTWORK, ClaimKind.LEGAL, priority=5)
    evidence = _evidence({}, Confidence.HIGH)
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.LOW


def test_factual_contradicted_high_confidence_priority_1_is_blocking() -> None:
    claim = _claim(ClaimCategory.STATISTIC, ClaimKind.FACTUAL, priority=1)
    evidence = _evidence({"verdict": "contradicted"}, Confidence.HIGH)
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.BLOCKING


def test_factual_contradicted_medium_confidence_is_high() -> None:
    claim = _claim(ClaimCategory.EVENT, ClaimKind.FACTUAL, priority=3)
    evidence = _evidence({"verdict": "contradicted"}, Confidence.MEDIUM)
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.HIGH


def test_factual_developing_story_is_at_least_medium() -> None:
    claim = _claim(ClaimCategory.EVENT, ClaimKind.FACTUAL, priority=5)
    evidence = _evidence({"verdict": "supported", "is_developing_story": True}, Confidence.HIGH)
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.MEDIUM


def test_factual_supported_is_low() -> None:
    claim = _claim(ClaimCategory.EVENT, ClaimKind.FACTUAL, priority=5)
    evidence = _evidence({"verdict": "supported"}, Confidence.HIGH)
    level, _, _ = prescore(evidence, claim)
    assert level == RiskLevel.LOW
