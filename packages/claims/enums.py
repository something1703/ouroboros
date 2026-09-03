"""Enumerations shared by every claim, evidence, and risk record. See DATA_MODEL.md §1.1."""

from __future__ import annotations

from enum import StrEnum


class ClaimKind(StrEnum):
    LEGAL = "legal"  # CLEAR
    FACTUAL = "factual"  # TRUE CUT


class ClaimCategory(StrEnum):
    # legal
    MUSIC = "music"  # song, cue, lyric, recording
    BRAND = "brand"  # trademark, logo, product, packaging
    PERSON = "person"  # real person, likeness, name, biography
    LOCATION = "location"  # real venue, landmark, private property
    ARTWORK = "artwork"  # painting, photo, sculpture, poster
    QUOTE = "quote"  # text from book/film/speech
    # factual
    EVENT = "event"  # something happened at a time/place
    STATISTIC = "statistic"  # a number, rate, ranking
    ATTRIBUTION = "attribution"  # who said/did/made something
    ARCHIVAL = "archival"  # provenance of footage/photo/audio
    IDENTITY = "identity"  # this person/thing on screen is who/what we say


LEGAL_CATEGORIES = frozenset(
    {
        ClaimCategory.MUSIC,
        ClaimCategory.BRAND,
        ClaimCategory.PERSON,
        ClaimCategory.LOCATION,
        ClaimCategory.ARTWORK,
        ClaimCategory.QUOTE,
    }
)
FACTUAL_CATEGORIES = frozenset(
    {
        ClaimCategory.EVENT,
        ClaimCategory.STATISTIC,
        ClaimCategory.ATTRIBUTION,
        ClaimCategory.ARCHIVAL,
        ClaimCategory.IDENTITY,
    }
)


class VerificationStatus(StrEnum):
    PENDING = "pending"
    TRIAGED = "triaged"
    VERIFYING = "verifying"
    VERIFIED = "verified"  # evidence exists (any confidence)
    ESCALATED = "escalated"  # pro Task in flight
    ERROR = "error"
    STALE = "stale"  # monitor detected change; re-verification pending


class RiskLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKING = "blocking"


# Ordered worst-to-none for comparisons (e.g. "did risk increase?").
RISK_LEVEL_ORDER: tuple[RiskLevel, ...] = (
    RiskLevel.BLOCKING,
    RiskLevel.HIGH,
    RiskLevel.MEDIUM,
    RiskLevel.LOW,
    RiskLevel.NONE,
)


class Confidence(StrEnum):  # mirrors Parallel Basis
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


CONFIDENCE_ORDER: tuple[Confidence, ...] = (
    Confidence.UNKNOWN,
    Confidence.LOW,
    Confidence.MEDIUM,
    Confidence.HIGH,
)
