"""Core domain types. Every agent, service, and view builds against these. See DATA_MODEL.md §1.

Change these only with an Alembic migration and a docs/DECISIONS.md entry (AGENTS.md §6.3).
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from packages.claims.enums import (
    ClaimCategory,
    ClaimKind,
    Confidence,
    RiskLevel,
    VerificationStatus,
)
from packages.claims.normalize import normalize_text
from packages.common.clock import Clock, SystemClock
from packages.common.ids import new_ulid

Channel = Literal["dialogue", "narration", "on_screen_text", "visual", "action_line"]
EvidenceMethod = Literal["search", "task", "responses", "entity_search", "extract", "grounding"]
Actor = Literal["ingest", "agent", "monitor", "reverify_worker", "human"]
MonitorType = Literal["snapshot", "event_stream"]
MonitorFrequency = Literal["1h", "1d", "1w"]
CostBand = Literal["none", "<1k", "1k-10k", "10k-100k", ">100k", "unknown"]
RemediationKind = Literal[
    "replace_brand", "replace_music", "reshoot", "recut", "obtain_release", "none"
]


class Project(BaseModel):
    """A film/TV production. See DATA_MODEL.md §3 `projects` table — this is its Pydantic mirror."""

    project_id: str
    studio_id: str
    title: str
    release_date: date | None = None
    shooting_countries: list[str] = Field(default_factory=list)
    distribution_territories: list[str] = Field(default_factory=list)
    budget_cap_usd: Decimal = Decimal("10.00")
    created_at: datetime


class Segment(BaseModel):
    """One transcript segment of a cut asset, absolute video time (already re-based past
    any per-chunk offset — see `packages/gemini_client/video.py`). Persisted so
    FactAgent can read a ±20s context window around a claim without re-running video
    understanding, and so `dashboard_api` can serve `GET /assets/{id}/segments`
    (PHASE_06.md §6.1, §6.4)."""

    t_start_ms: int
    t_end_ms: int
    speaker: str | None = None
    transcript: str


class Asset(BaseModel):
    """A single uploaded script or cut. See DATA_MODEL.md §3 `assets` table."""

    asset_id: str
    project_id: str
    kind: Literal["script", "cut"]
    gcs_uri: str
    language: str | None = None
    page_count: int | None = None
    duration_ms: int | None = None
    segments: list[Segment] = Field(default_factory=list)
    proxy_uri: str | None = None  # low-res proxy MP4, gs://..., PHASE_06.md §6.4
    poster_uri: str | None = None  # poster frame JPEG, gs://..., PHASE_06.md §6.4
    ingested_at: datetime | None = None

    @staticmethod
    def compute_id(*, bucket: str, name: str, generation: str) -> str:
        """Deterministic asset_id from the GCS object identity that triggered ingest.

        sha256(bucket|name|generation)[:24]

        `generation` (not just bucket/name) is the idempotency key PHASE_03.md §3.1
        calls for: Eventarc/Pub/Sub delivery is at-least-once, so the same
        `object.finalized` CloudEvent can arrive twice for the same underlying upload —
        this makes re-processing it a no-op via ClaimRepo.upsert's primary-key semantics,
        without needing separate bucket/name/generation columns on `assets`.
        """
        raw = f"{bucket}|{name}|{generation}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


class SourceRef(BaseModel):
    """Where in the source asset a claim came from — exactly one of the script/video field groups is set."""

    asset_id: str
    # script
    page: int | None = None
    scene_number: str | None = None
    scene_heading: str | None = None
    # video
    t_start_ms: int | None = None
    t_end_ms: int | None = None
    channel: Channel | None = None
    excerpt: str = Field(max_length=500)  # verbatim text that produced the claim
    # dedupe bookkeeping (ingest merges repeats of the same normalized_text+category
    # within one asset into a single claim; see PHASE_03.md §3.5)
    occurrences: int = 1
    all_refs: list[dict[str, object]] = Field(default_factory=list)


class Claim(BaseModel):
    claim_id: str
    project_id: str
    studio_id: str
    kind: ClaimKind
    category: ClaimCategory
    entity_text: str  # canonical surface form, e.g. "Coca-Cola", "Bohemian Rhapsody"
    normalized_text: str  # lowercase, punctuation-stripped, for hashing/dedupe
    claim_text: str  # one sentence, e.g. "A Coca-Cola can is visible on the table in Sc. 12"
    language: str  # BCP-47 of the source text
    source: SourceRef
    jurisdictions: list[str]  # ISO alpha-2 codes; from project.distribution_territories
    priority: int = Field(ge=1, le=5, default=3)  # 1 (highest) - 5; set by ClaimTriage
    status: VerificationStatus = VerificationStatus.PENDING
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def compute_id(
        *,
        project_id: str,
        category: ClaimCategory,
        normalized_text: str,
        asset_id: str,
        page_or_t_start: int | None,
    ) -> str:
        """Deterministic claim_id. Re-ingesting the same script produces the same IDs.

        sha256(project_id|category|normalized_text|asset_id|page_or_t_start)[:24]
        """
        location = "" if page_or_t_start is None else str(page_or_t_start)
        raw = f"{project_id}|{category.value}|{normalized_text}|{asset_id}|{location}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    @classmethod
    def new(
        cls,
        *,
        project_id: str,
        studio_id: str,
        kind: ClaimKind,
        category: ClaimCategory,
        entity_text: str,
        claim_text: str,
        language: str,
        source: SourceRef,
        jurisdictions: list[str],
        priority: int = 3,
        clock: Clock | None = None,
    ) -> Claim:
        """Factory used by ingest: computes normalized_text and claim_id, stamps timestamps."""
        clock = clock or SystemClock()
        normalized = normalize_text(entity_text)
        page_or_t_start = source.page if source.page is not None else source.t_start_ms
        claim_id = cls.compute_id(
            project_id=project_id,
            category=category,
            normalized_text=normalized,
            asset_id=source.asset_id,
            page_or_t_start=page_or_t_start,
        )
        now = clock.now()
        return cls(
            claim_id=claim_id,
            project_id=project_id,
            studio_id=studio_id,
            kind=kind,
            category=category,
            entity_text=entity_text,
            normalized_text=normalized,
            claim_text=claim_text,
            language=language,
            source=source,
            jurisdictions=jurisdictions,
            priority=priority,
            created_at=now,
            updated_at=now,
        )


class Citation(BaseModel):
    url: str
    excerpt: str | None = None
    retrieved_at: datetime


class FieldBasis(BaseModel):
    """1:1 with Parallel's per-field Basis."""

    field: str
    citations: list[Citation]
    reasoning: str
    confidence: Confidence


class Evidence(BaseModel):
    """One per verification cycle."""

    evidence_id: str = Field(default_factory=new_ulid)
    claim_id: str
    cycle: int = Field(ge=1)  # 1 = first verification, 2+ = re-verification
    method: EvidenceMethod
    parallel_run_id: str | None = None  # trun_..., or response id
    previous_interaction_id: str | None = None
    processor: str | None = None  # core-fast, pro, medium...
    output: dict[
        str, object
    ]  # structured Task/Responses content, schema per category (DATA_MODEL.md §2)
    basis: list[FieldBasis]
    overall_confidence: Confidence  # min over required fields
    cost_usd: Decimal = Decimal("0")
    created_at: datetime


class Risk(BaseModel):
    """Current risk for a claim; history kept separately (risk_history)."""

    claim_id: str
    evidence_id: str
    level: RiskLevel
    score: float = Field(ge=0.0, le=1.0)
    rationale: str
    cost_band: CostBand | None = None
    remediation_suggested: bool = False
    remediation_kind: RemediationKind = "none"
    territory_flags: dict[str, RiskLevel] = Field(default_factory=dict)  # per jurisdiction
    assessed_at: datetime


class VerificationEvent(BaseModel):
    """Append-only audit trail entry."""

    event_id: str = Field(default_factory=new_ulid)
    claim_id: str
    at: datetime
    actor: Actor
    from_status: VerificationStatus | None
    to_status: VerificationStatus
    note: str
    ref: dict[str, object] = Field(
        default_factory=dict
    )  # {"monitor_id":..., "event_id":..., "run_id":..., "user":...}


class MonitorRecord(BaseModel):
    monitor_id: str  # Parallel monitor id
    claim_id: str
    type: MonitorType
    task_run_id: str | None = None  # for snapshot
    query: str | None = None  # for event_stream
    frequency: MonitorFrequency
    status: Literal["active", "cancelled"]
    last_event_at: datetime | None = None
    created_at: datetime
