"""Repository layer. One class per table, upsert-by-id semantics, Pydantic in and out.

`record_evidence_and_status` is the one cross-table transactional helper: evidence insert +
history append + claim status update, atomically, because that's the write pattern every
specialist agent and the reverify_worker actually needs (PHASE_02.md §2.2).

Every method takes an open `Session` — callers control transaction boundaries with
`packages.ledger.db.session_scope()`. Nothing here commits.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from packages.claims.enums import VerificationStatus
from packages.claims.models import (
    Asset,
    Claim,
    Evidence,
    MonitorRecord,
    Project,
    Risk,
    SourceRef,
    VerificationEvent,
)
from packages.common.errors import NotFound
from packages.ledger.tables import (
    AssetRow,
    ClaimRow,
    CostEventRow,
    EvidenceRow,
    MonitorRow,
    PriorDecisionRow,
    ProjectRow,
    RiskHistoryRow,
    RiskRow,
    VerificationHistoryRow,
)


def _project_from_row(row: ProjectRow) -> Project:
    return Project(
        project_id=row.project_id,
        studio_id=row.studio_id,
        title=row.title,
        release_date=row.release_date,
        shooting_countries=list(row.shooting_countries),
        distribution_territories=list(row.distribution_territories),
        budget_cap_usd=row.budget_cap_usd,
        created_at=row.created_at,
    )


class ProjectRepo:
    @staticmethod
    def upsert(session: Session, project: Project) -> None:
        stmt = pg_insert(ProjectRow).values(
            project_id=project.project_id,
            studio_id=project.studio_id,
            title=project.title,
            release_date=project.release_date,
            shooting_countries=project.shooting_countries,
            distribution_territories=project.distribution_territories,
            budget_cap_usd=project.budget_cap_usd,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProjectRow.project_id],
            set_={
                "studio_id": stmt.excluded.studio_id,
                "title": stmt.excluded.title,
                "release_date": stmt.excluded.release_date,
                "shooting_countries": stmt.excluded.shooting_countries,
                "distribution_territories": stmt.excluded.distribution_territories,
                "budget_cap_usd": stmt.excluded.budget_cap_usd,
            },
        )
        session.execute(stmt)

    @staticmethod
    def get(session: Session, project_id: str) -> Project | None:
        row = session.get(ProjectRow, project_id)
        return _project_from_row(row) if row else None

    @staticmethod
    def require(session: Session, project_id: str) -> Project:
        project = ProjectRepo.get(session, project_id)
        if project is None:
            raise NotFound("project", project_id)
        return project

    @staticmethod
    def spend(session: Session, project_id: str) -> Decimal:
        """Sum of every cost_events row for this project. Used by the cost meter (packages/parallel_client/cost.py)."""
        total = session.scalar(
            select(func.coalesce(func.sum(CostEventRow.cost_usd), 0)).where(
                CostEventRow.project_id == project_id
            )
        )
        return Decimal(total or 0)


def _asset_from_row(row: AssetRow) -> Asset:
    return Asset(
        asset_id=row.asset_id,
        project_id=row.project_id,
        kind=row.kind,
        gcs_uri=row.gcs_uri,
        language=row.language,
        page_count=row.page_count,
        duration_ms=row.duration_ms,
        ingested_at=row.ingested_at,
    )


class AssetRepo:
    @staticmethod
    def upsert(session: Session, asset: Asset) -> None:
        stmt = pg_insert(AssetRow).values(
            asset_id=asset.asset_id,
            project_id=asset.project_id,
            kind=asset.kind,
            gcs_uri=asset.gcs_uri,
            language=asset.language,
            page_count=asset.page_count,
            duration_ms=asset.duration_ms,
            ingested_at=asset.ingested_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AssetRow.asset_id],
            set_={
                "gcs_uri": stmt.excluded.gcs_uri,
                "language": stmt.excluded.language,
                "page_count": stmt.excluded.page_count,
                "duration_ms": stmt.excluded.duration_ms,
                "ingested_at": stmt.excluded.ingested_at,
            },
        )
        session.execute(stmt)

    @staticmethod
    def get(session: Session, asset_id: str) -> Asset | None:
        row = session.get(AssetRow, asset_id)
        return _asset_from_row(row) if row else None

    @staticmethod
    def list_by_project(session: Session, project_id: str) -> list[Asset]:
        rows = session.scalars(select(AssetRow).where(AssetRow.project_id == project_id)).all()
        return [_asset_from_row(r) for r in rows]


def _claim_from_row(row: ClaimRow) -> Claim:
    return Claim(
        claim_id=row.claim_id,
        project_id=row.project_id,
        studio_id=row.studio_id,
        kind=row.kind,
        category=row.category,
        entity_text=row.entity_text,
        normalized_text=row.normalized_text,
        claim_text=row.claim_text,
        language=row.language,
        source=SourceRef.model_validate(row.source),
        jurisdictions=list(row.jurisdictions),
        priority=row.priority,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ClaimRepo:
    @staticmethod
    def upsert(session: Session, claim: Claim) -> None:
        stmt = pg_insert(ClaimRow).values(
            claim_id=claim.claim_id,
            project_id=claim.project_id,
            studio_id=claim.studio_id,
            kind=claim.kind.value,
            category=claim.category.value,
            entity_text=claim.entity_text,
            normalized_text=claim.normalized_text,
            claim_text=claim.claim_text,
            language=claim.language,
            source=claim.source.model_dump(mode="json"),
            jurisdictions=claim.jurisdictions,
            priority=claim.priority,
            status=claim.status.value,
            created_at=claim.created_at,
            updated_at=claim.updated_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ClaimRow.claim_id],
            set_={
                # Merge dedupe bookkeeping (source.occurrences/all_refs) rather than clobbering
                # it: the caller is expected to have already merged `source` before calling.
                "entity_text": stmt.excluded.entity_text,
                "claim_text": stmt.excluded.claim_text,
                "source": stmt.excluded.source,
                "jurisdictions": stmt.excluded.jurisdictions,
                "priority": stmt.excluded.priority,
                "status": stmt.excluded.status,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        session.execute(stmt)

    @staticmethod
    def upsert_many(session: Session, claims: list[Claim]) -> None:
        for claim in claims:
            ClaimRepo.upsert(session, claim)

    @staticmethod
    def get(session: Session, claim_id: str) -> Claim | None:
        row = session.get(ClaimRow, claim_id)
        return _claim_from_row(row) if row else None

    @staticmethod
    def require(session: Session, claim_id: str) -> Claim:
        claim = ClaimRepo.get(session, claim_id)
        if claim is None:
            raise NotFound("claim", claim_id)
        return claim

    @staticmethod
    def list_by_project(
        session: Session,
        project_id: str,
        *,
        status: VerificationStatus | None = None,
        category: str | None = None,
        limit: int = 50,
    ) -> list[Claim]:
        stmt = select(ClaimRow).where(ClaimRow.project_id == project_id)
        if status is not None:
            stmt = stmt.where(ClaimRow.status == status.value)
        if category is not None:
            stmt = stmt.where(ClaimRow.category == category)
        stmt = stmt.limit(limit)
        rows = session.scalars(stmt).all()
        return [_claim_from_row(r) for r in rows]

    @staticmethod
    def set_status(session: Session, claim_id: str, status: VerificationStatus) -> None:
        claim_row = session.get(ClaimRow, claim_id)
        if claim_row is None:
            raise NotFound("claim", claim_id)
        claim_row.status = status.value


def _evidence_from_row(row: EvidenceRow) -> Evidence:
    return Evidence(
        evidence_id=row.evidence_id,
        claim_id=row.claim_id,
        cycle=row.cycle,
        method=row.method,
        parallel_run_id=row.parallel_run_id,
        previous_interaction_id=row.previous_interaction_id,
        processor=row.processor,
        output=row.output,
        basis=row.basis,
        overall_confidence=row.overall_confidence,
        cost_usd=row.cost_usd,
        created_at=row.created_at,
    )


class EvidenceRepo:
    @staticmethod
    def insert(session: Session, evidence: Evidence) -> None:
        session.add(
            EvidenceRow(
                evidence_id=evidence.evidence_id,
                claim_id=evidence.claim_id,
                cycle=evidence.cycle,
                method=evidence.method,
                parallel_run_id=evidence.parallel_run_id,
                previous_interaction_id=evidence.previous_interaction_id,
                processor=evidence.processor,
                output=evidence.output,
                basis=[b.model_dump(mode="json") for b in evidence.basis],
                overall_confidence=evidence.overall_confidence.value,
                cost_usd=evidence.cost_usd,
                created_at=evidence.created_at,
            )
        )

    @staticmethod
    def latest_for_claim(session: Session, claim_id: str) -> Evidence | None:
        row = session.scalars(
            select(EvidenceRow)
            .where(EvidenceRow.claim_id == claim_id)
            .order_by(EvidenceRow.cycle.desc())
            .limit(1)
        ).first()
        return _evidence_from_row(row) if row else None

    @staticmethod
    def history_for_claim(session: Session, claim_id: str) -> list[Evidence]:
        rows = session.scalars(
            select(EvidenceRow).where(EvidenceRow.claim_id == claim_id).order_by(EvidenceRow.cycle)
        ).all()
        return [_evidence_from_row(r) for r in rows]

    @staticmethod
    def next_cycle(session: Session, claim_id: str) -> int:
        latest = EvidenceRepo.latest_for_claim(session, claim_id)
        return 1 if latest is None else latest.cycle + 1


def _risk_from_row(row: RiskRow) -> Risk:
    return Risk(
        claim_id=row.claim_id,
        evidence_id=row.evidence_id,
        level=row.level,
        score=row.score,
        rationale=row.rationale,
        cost_band=row.cost_band,
        remediation_suggested=row.remediation_suggested,
        remediation_kind=row.remediation_kind or "none",
        territory_flags=row.territory_flags,
        assessed_at=row.assessed_at,
    )


class RiskRepo:
    @staticmethod
    def upsert(session: Session, risk: Risk) -> None:
        stmt = pg_insert(RiskRow).values(
            claim_id=risk.claim_id,
            evidence_id=risk.evidence_id,
            level=risk.level.value,
            score=risk.score,
            rationale=risk.rationale,
            cost_band=risk.cost_band,
            remediation_suggested=risk.remediation_suggested,
            remediation_kind=risk.remediation_kind,
            territory_flags={k: v.value for k, v in risk.territory_flags.items()},
            assessed_at=risk.assessed_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[RiskRow.claim_id],
            set_={
                "evidence_id": stmt.excluded.evidence_id,
                "level": stmt.excluded.level,
                "score": stmt.excluded.score,
                "rationale": stmt.excluded.rationale,
                "cost_band": stmt.excluded.cost_band,
                "remediation_suggested": stmt.excluded.remediation_suggested,
                "remediation_kind": stmt.excluded.remediation_kind,
                "territory_flags": stmt.excluded.territory_flags,
                "assessed_at": stmt.excluded.assessed_at,
            },
        )
        session.execute(stmt)
        session.add(
            RiskHistoryRow(
                claim_id=risk.claim_id,
                evidence_id=risk.evidence_id,
                level=risk.level.value,
                score=risk.score,
                rationale=risk.rationale,
                cost_band=risk.cost_band,
                remediation_suggested=risk.remediation_suggested,
                remediation_kind=risk.remediation_kind,
                territory_flags={k: v.value for k, v in risk.territory_flags.items()},
                assessed_at=risk.assessed_at,
            )
        )

    @staticmethod
    def get(session: Session, claim_id: str) -> Risk | None:
        row = session.get(RiskRow, claim_id)
        return _risk_from_row(row) if row else None


class HistoryRepo:
    @staticmethod
    def append(session: Session, event: VerificationEvent) -> None:
        session.add(
            VerificationHistoryRow(
                event_id=event.event_id,
                claim_id=event.claim_id,
                at=event.at,
                actor=event.actor,
                from_status=event.from_status.value if event.from_status else None,
                to_status=event.to_status.value,
                note=event.note,
                ref=event.ref,
            )
        )

    @staticmethod
    def for_claim(session: Session, claim_id: str) -> list[VerificationEvent]:
        rows = session.scalars(
            select(VerificationHistoryRow)
            .where(VerificationHistoryRow.claim_id == claim_id)
            .order_by(VerificationHistoryRow.at)
        ).all()
        return [
            VerificationEvent(
                event_id=r.event_id,
                claim_id=r.claim_id,
                at=r.at,
                actor=r.actor,
                from_status=r.from_status,
                to_status=r.to_status,
                note=r.note or "",
                ref=r.ref or {},
            )
            for r in rows
        ]


class MonitorRepo:
    @staticmethod
    def upsert(session: Session, monitor: MonitorRecord) -> None:
        stmt = pg_insert(MonitorRow).values(
            monitor_id=monitor.monitor_id,
            claim_id=monitor.claim_id,
            type=monitor.type,
            task_run_id=monitor.task_run_id,
            query=monitor.query,
            frequency=monitor.frequency,
            status=monitor.status,
            last_event_at=monitor.last_event_at,
            created_at=monitor.created_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[MonitorRow.monitor_id],
            set_={
                "frequency": stmt.excluded.frequency,
                "status": stmt.excluded.status,
                "last_event_at": stmt.excluded.last_event_at,
            },
        )
        session.execute(stmt)

    @staticmethod
    def list_active_for_project(session: Session, project_id: str) -> list[MonitorRecord]:
        rows = session.scalars(
            select(MonitorRow)
            .join(ClaimRow, ClaimRow.claim_id == MonitorRow.claim_id)
            .where(ClaimRow.project_id == project_id, MonitorRow.status == "active")
        ).all()
        return [
            MonitorRecord(
                monitor_id=r.monitor_id,
                claim_id=r.claim_id,
                type=r.type,
                task_run_id=r.task_run_id,
                query=r.query,
                frequency=r.frequency,
                status=r.status,
                last_event_at=r.last_event_at,
                created_at=r.created_at,
            )
            for r in rows
        ]


class CostRepo:
    @staticmethod
    def record(
        session: Session,
        *,
        project_id: str,
        claim_id: str | None,
        api: str,
        sku: str | None,
        units: int,
        cost_usd: Decimal,
        at: object,
    ) -> None:
        session.add(
            CostEventRow(
                project_id=project_id,
                claim_id=claim_id,
                api=api,
                sku=sku,
                units=units,
                cost_usd=cost_usd,
                at=at,
            )
        )


class PriorDecisionRepo:
    @staticmethod
    def add(
        session: Session,
        *,
        studio_id: str,
        category: str | None,
        entity_normalized: str,
        decision: str,
        note: str | None,
        decided_at: object,
    ) -> None:
        session.add(
            PriorDecisionRow(
                studio_id=studio_id,
                category=category,
                entity_normalized=entity_normalized,
                decision=decision,
                note=note,
                decided_at=decided_at,
            )
        )

    @staticmethod
    def find(session: Session, studio_id: str, entity_normalized: str) -> list[PriorDecisionRow]:
        return list(
            session.scalars(
                select(PriorDecisionRow).where(
                    PriorDecisionRow.studio_id == studio_id,
                    PriorDecisionRow.entity_normalized == entity_normalized,
                )
            ).all()
        )


def record_evidence_and_status(
    session: Session,
    *,
    evidence: Evidence,
    event: VerificationEvent,
    new_status: VerificationStatus,
) -> None:
    """Evidence insert + history append + claim status update, in one transaction.

    Wrap the call in `packages.ledger.db.session_scope()` for atomic commit — this
    function itself never commits.
    """
    EvidenceRepo.insert(session, evidence)
    HistoryRepo.append(session, event)
    ClaimRepo.set_status(session, evidence.claim_id, new_status)


__all__ = [
    "AssetRepo",
    "ClaimRepo",
    "CostRepo",
    "EvidenceRepo",
    "HistoryRepo",
    "MonitorRepo",
    "PriorDecisionRepo",
    "ProjectRepo",
    "RiskRepo",
    "record_evidence_and_status",
]
