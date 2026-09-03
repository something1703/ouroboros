"""Deterministic risk pre-scoring. RiskAssessor (ADK_AGENTS.md §2.3) may adjust the result
±1 level with an LLM rationale, but this function is what makes that adjustment auditable —
it must run first, standalone, and produce the same answer for the same Evidence every time.
"""

from __future__ import annotations

from packages.claims.enums import ClaimCategory, ClaimKind, Confidence, RiskLevel
from packages.claims.models import Claim, Evidence

_REFUSAL_KEYWORDS = ("refus", "declin", "will not license", "does not license", "denied")


def prescore(evidence: Evidence, claim: Claim) -> tuple[RiskLevel, float, list[str]]:
    """Returns (level, score in [0,1], rationale bullets)."""
    if claim.kind == ClaimKind.LEGAL:
        return _prescore_legal(evidence, claim)
    return _prescore_factual(evidence, claim)


def _mentions_refusal(text: object) -> bool:
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in _REFUSAL_KEYWORDS)


def _prescore_legal(evidence: Evidence, claim: Claim) -> tuple[RiskLevel, float, list[str]]:
    output = evidence.output
    confidence = evidence.overall_confidence

    # --- blocking ---------------------------------------------------------
    if (
        claim.category == ClaimCategory.PERSON
        and output.get("is_living") is True
        and output.get("consent_recommended") is True
    ):
        return (
            RiskLevel.BLOCKING,
            1.0,
            ["living person; consent recommended and none on file"],
        )

    if claim.category == ClaimCategory.BRAND and output.get("known_litigiousness") == "high":
        return RiskLevel.BLOCKING, 0.95, ["brand has a documented high litigiousness rating"]

    if claim.category == ClaimCategory.MUSIC and _mentions_refusal(
        output.get("known_sync_restrictions")
    ):
        return RiskLevel.BLOCKING, 0.95, ["documented refusal to license this work"]

    # Public domain overrides everything below it in the rubric ("low: ...public
    # domain, or generic" per ADK_AGENTS.md §2.3) regardless of confidence level.
    if output.get("is_public_domain") is True:
        return RiskLevel.LOW, 0.1, ["public domain"]

    # --- high ---------------------------------------------------------------
    cost_band = output.get("typical_sync_cost_band")
    if not isinstance(cost_band, str):
        cost_band = None

    if confidence == Confidence.LOW and claim.priority <= 2:
        return (
            RiskLevel.HIGH,
            0.75,
            [f"low-confidence evidence on a priority-{claim.priority} claim"],
        )
    if cost_band in ("10k-100k", ">100k"):
        return RiskLevel.HIGH, 0.7, [f"typical clearance cost band is {cost_band}"]

    # --- medium ---------------------------------------------------------------
    if confidence == Confidence.MEDIUM:
        return RiskLevel.MEDIUM, 0.5, ["medium-confidence evidence"]
    if cost_band == "1k-10k":
        return RiskLevel.MEDIUM, 0.45, ["typical clearance cost band is 1k-10k"]

    # --- low ---------------------------------------------------------------
    if confidence == Confidence.HIGH:
        return RiskLevel.LOW, 0.2, ["high-confidence evidence, no blocking signal"]

    return RiskLevel.LOW, 0.25, ["no strong risk signal found in evidence; defaulting to low"]


def _prescore_factual(evidence: Evidence, claim: Claim) -> tuple[RiskLevel, float, list[str]]:
    output = evidence.output
    confidence = evidence.overall_confidence
    verdict = output.get("verdict")
    is_developing = bool(output.get("is_developing_story", False))

    if verdict == "contradicted" and confidence == Confidence.HIGH and claim.priority == 1:
        return (
            RiskLevel.BLOCKING,
            1.0,
            ["contradicted with high confidence on a priority-1 claim"],
        )

    if verdict in ("contradicted", "partially_supported") and confidence == Confidence.MEDIUM:
        return RiskLevel.HIGH, 0.7, [f"{verdict} with medium confidence"]

    if verdict == "unverifiable" and claim.priority <= 2:
        return (
            RiskLevel.MEDIUM,
            0.5,
            [f"unverifiable on a priority-{claim.priority} claim"],
        )
    if is_developing:
        return RiskLevel.MEDIUM, 0.45, ["facts likely to change before release (developing story)"]

    if verdict == "supported":
        return RiskLevel.LOW, 0.1, ["supported by evidence"]

    return RiskLevel.LOW, 0.25, ["no strong risk signal found in evidence; defaulting to low"]
