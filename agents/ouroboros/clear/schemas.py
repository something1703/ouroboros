"""Structured `output_schema`s for CLEAR's LlmAgents. See ADK_AGENTS.md §2."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkippedClaim(BaseModel):
    claim_id: str
    reason: str


class TriageBatches(BaseModel):
    music: list[str] = Field(default_factory=list)
    brand: list[str] = Field(default_factory=list)
    person: list[str] = Field(default_factory=list)
    location_artwork: list[str] = Field(default_factory=list)


class TriageOutput(BaseModel):
    batches: TriageBatches
    skipped: list[SkippedClaim] = Field(default_factory=list)


class SpecialistOutput(BaseModel):
    """`<category>_results`, ADK_AGENTS.md §2.2."""

    verified: list[str] = Field(default_factory=list)
    escalated: list[str] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)


class RiskSummary(BaseModel):
    claim_id: str
    level: str
    score: float


class RiskAssessorOutput(BaseModel):
    """`risks`, ADK_AGENTS.md §2.3."""

    risks: list[RiskSummary] = Field(default_factory=list)


class ReporterOutput(BaseModel):
    """`report`, ADK_AGENTS.md §2.4."""

    summary_md: str
    monitors_created: int
    claims_by_risk: dict[str, int] = Field(default_factory=dict)
