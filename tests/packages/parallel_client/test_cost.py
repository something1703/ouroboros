from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from packages.claims.models import Project
from packages.common.errors import BudgetExceeded
from packages.ledger.repositories import ProjectRepo
from packages.parallel_client.cost import CostMeter, gemini_cost, price_for

pytestmark = pytest.mark.usefixtures("engine")

_NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _project(project_id: str = "demo", budget_cap_usd: Decimal = Decimal("10.00")) -> Project:
    return Project(
        project_id=project_id,
        studio_id="studio-1",
        title="Demo Film",
        budget_cap_usd=budget_cap_usd,
        created_at=_NOW,
    )


def test_price_for_known_sku() -> None:
    assert price_for("search.fast") == Decimal("0.001")
    assert price_for("task.core-fast") == Decimal("0.025")


def test_price_for_unknown_sku_raises() -> None:
    with pytest.raises(KeyError):
        price_for("search.nonexistent")


def test_price_for_scales_with_units() -> None:
    assert price_for("search.extra_result", units=5) == Decimal("0.005")


def test_gemini_cost_computation() -> None:
    cost = gemini_cost("gemini-3.5-flash", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == Decimal("0.075") + Decimal("0.30")


def test_gemini_cost_unknown_model_raises() -> None:
    with pytest.raises(KeyError):
        gemini_cost("gemini-nonexistent", input_tokens=1, output_tokens=1)


def test_cost_meter_records_estimate(db_session: Session) -> None:
    project = _project()
    ProjectRepo.upsert(db_session, project)
    db_session.commit()

    with CostMeter(db_session, project.project_id, api="search", sku="search.fast") as meter:
        assert meter.estimated_cost_usd == Decimal("0.001")
    db_session.commit()

    spend = ProjectRepo.spend(db_session, project.project_id)
    assert spend == Decimal("0.001")


def test_cost_meter_raises_when_over_budget(db_session: Session) -> None:
    project = _project(budget_cap_usd=Decimal("0.03"))
    ProjectRepo.upsert(db_session, project)
    db_session.commit()

    # First call fits under the cap (0.025 <= 0.03).
    with CostMeter(db_session, project.project_id, api="task", sku="task.core-fast"):
        pass
    db_session.commit()

    with (
        pytest.raises(BudgetExceeded),
        CostMeter(db_session, project.project_id, api="task", sku="task.pro"),
    ):
        pass
    db_session.rollback()


def test_cost_meter_records_actual_correction(db_session: Session) -> None:
    project = _project()
    ProjectRepo.upsert(db_session, project)
    db_session.commit()

    with CostMeter(db_session, project.project_id, api="search", sku="search.fast") as meter:
        pass
    meter.record_actual(Decimal("0.003"))  # e.g. extra results beyond the estimate
    db_session.commit()

    spend = ProjectRepo.spend(db_session, project.project_id)
    assert spend == Decimal("0.003")


def test_cost_meter_no_correction_row_when_actual_matches_estimate(db_session: Session) -> None:
    project = _project()
    ProjectRepo.upsert(db_session, project)
    db_session.commit()

    with CostMeter(db_session, project.project_id, api="search", sku="search.fast") as meter:
        pass
    meter.record_actual(meter.estimated_cost_usd)
    db_session.commit()

    spend = ProjectRepo.spend(db_session, project.project_id)
    assert spend == Decimal("0.001")  # unchanged — no correction row added
