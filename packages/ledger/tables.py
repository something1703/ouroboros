"""SQLAlchemy 2.0 declarative models — one class per table in DATA_MODEL.md §3.

Change these only with an Alembic migration and a docs/DECISIONS.md entry (AGENTS.md §6.3).
The repository layer (packages/ledger/repositories.py) is the only code that touches these
directly; everything else works with the Pydantic domain models in packages/claims.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(Text, primary_key=True)
    studio_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    release_date: Mapped[date | None] = mapped_column(Date)
    shooting_countries: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default="{}"
    )
    distribution_territories: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default="{}"
    )
    budget_cap_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("10.00")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AssetRow(Base):
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("projects.project_id"))
    kind: Mapped[str] = mapped_column(Text)
    gcs_uri: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("kind in ('script','cut')", name="assets_kind_check"),)


class ClaimRow(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("projects.project_id"))
    studio_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    entity_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    jurisdictions: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_claims_project_status", "project_id", "status"),
        Index("ix_claims_project_category", "project_id", "category"),
    )


class EvidenceRow(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(Text, primary_key=True)
    claim_id: Mapped[str] = mapped_column(Text, ForeignKey("claims.claim_id"))
    cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    parallel_run_id: Mapped[str | None] = mapped_column(Text)
    previous_interaction_id: Mapped[str | None] = mapped_column(Text)
    processor: Mapped[str | None] = mapped_column(Text)
    output: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    basis: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    overall_confidence: Mapped[str] = mapped_column(Text, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_evidence_claim_cycle", "claim_id", "cycle"),)


class RiskRow(Base):
    __tablename__ = "risk"

    claim_id: Mapped[str] = mapped_column(Text, ForeignKey("claims.claim_id"), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(Text, ForeignKey("evidence.evidence_id"))
    level: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    cost_band: Mapped[str | None] = mapped_column(Text)
    remediation_suggested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remediation_kind: Mapped[str | None] = mapped_column(Text)
    territory_flags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RiskHistoryRow(Base):
    """Append-only: one row per risk assessment, ever. `risk` holds only the latest."""

    __tablename__ = "risk_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    cost_band: Mapped[str | None] = mapped_column(Text)
    remediation_suggested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remediation_kind: Mapped[str | None] = mapped_column(Text)
    territory_flags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VerificationHistoryRow(Base):
    __tablename__ = "verification_history"

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    claim_id: Mapped[str] = mapped_column(Text, ForeignKey("claims.claim_id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    ref: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    __table_args__ = (Index("ix_verification_history_claim_at", "claim_id", "at"),)


class MonitorRow(Base):
    __tablename__ = "monitors"

    monitor_id: Mapped[str] = mapped_column(Text, primary_key=True)
    claim_id: Mapped[str] = mapped_column(Text, ForeignKey("claims.claim_id"))
    type: Mapped[str] = mapped_column(Text, nullable=False)
    task_run_id: Mapped[str | None] = mapped_column(Text)
    query: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CostEventRow(Base):
    __tablename__ = "cost_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[str | None] = mapped_column(Text)
    claim_id: Mapped[str | None] = mapped_column(Text)
    api: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str | None] = mapped_column(Text)
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_cost_events_project_at", "project_id", "at"),)


class PriorDecisionRow(Base):
    """Studio memory: human-entered or imported prior clearance decisions."""

    __tablename__ = "prior_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    studio_id: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    entity_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_prior_decisions_studio_entity", "studio_id", "entity_normalized"),)
