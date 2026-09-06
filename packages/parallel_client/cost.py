"""Cost metering for Parallel and Gemini calls. Every Parallel call is metered *before*
execution (estimate, from config/parallel.py's price table) and corrected *after* if the
actual usage differs, per AGENTS.md §4.2 and PARALLEL_INTEGRATION.md §2.

Landing this in Phase 2 (before packages/parallel_client has any actual API wrappers,
which are Phase 4) is deliberate — CostMeter and BudgetExceeded must exist before the
first real Parallel call in Phase 4 can be metered.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType

from sqlalchemy.orm import Session

from config.models import GEMINI_PRICE_PER_1M_TOKENS_USD
from config.parallel import PRICE_TABLE_USD, PROJECT_BUDGET_USD_DEFAULT
from packages.common.errors import BudgetExceeded
from packages.common.logging import get_logger
from packages.ledger import bq_stream
from packages.ledger.repositories import CostRepo, ProjectRepo


def price_for(sku: str, *, units: int = 1) -> Decimal:
    """Look up the price for one Parallel SKU (e.g. 'search.fast', 'task.core-fast')."""
    base = PRICE_TABLE_USD.get(sku)
    if base is None:
        raise KeyError(f"unknown Parallel SKU: {sku!r}")
    return Decimal(str(base)) * units


def gemini_cost(model: str, *, input_tokens: int, output_tokens: int) -> Decimal:
    """Token-based cost estimate for a Gemini call, from usage_metadata."""
    prices = GEMINI_PRICE_PER_1M_TOKENS_USD.get(model)
    if prices is None:
        raise KeyError(f"unknown Gemini model: {model!r}")
    million = Decimal(1_000_000)
    input_cost = Decimal(str(prices["input"])) * input_tokens / million
    output_cost = Decimal(str(prices["output"])) * output_tokens / million
    return input_cost + output_cost


def check_budget(session: Session, project_id: str) -> None:
    """Pre-flight check (`cost.check` tool, ADK_AGENTS.md §0): raises `BudgetExceeded`
    if the project is *already* over its cap, without recording anything — a specialist
    calls this once per claim before doing any real work, so a batch stops cleanly
    (PARALLEL_INTEGRATION.md §6: "mark remaining claims pending with note budget")
    rather than exceeding the cap mid-batch on an already-blown budget."""
    spent = ProjectRepo.spend(session, project_id)
    project = ProjectRepo.get(session, project_id)
    cap = project.budget_cap_usd if project else Decimal(str(PROJECT_BUDGET_USD_DEFAULT))
    # PHASE_09.md §9.4's "spend > 80% of cap" alert -- logged here, not just checked,
    # since this is the one place both real-time-DB-backed callers (reverify_worker)
    # already call before every priced action.
    if cap > 0 and spent / cap >= Decimal("0.8"):
        get_logger(__name__).warning(
            "budget_80_percent",
            project_id=project_id,
            spend_usd=float(spent),
            cap_usd=float(cap),
        )
    if spent > cap:
        raise BudgetExceeded(project_id, float(spent), float(cap))


class CostMeter:
    """`with CostMeter(session, project_id, api="search", sku="search.fast", claim_id=claim_id):`

    Records an estimated cost_events row *before* the wrapped call runs, raising
    BudgetExceeded first if that estimate would push the project over its
    budget_cap_usd. Call `record_actual()` after the real response comes back if its
    usage-reported cost differs from the estimate — this appends a correction row
    rather than mutating the estimate, keeping cost_events an honest append-only log.
    """

    def __init__(
        self,
        session: Session,
        project_id: str,
        *,
        api: str,
        sku: str,
        claim_id: str | None = None,
        units: int = 1,
        budget_cap_usd: Decimal | None = None,
    ) -> None:
        self._session = session
        self._project_id = project_id
        self._api = api
        self._sku = sku
        self._claim_id = claim_id
        self._units = units
        self._budget_cap_usd = budget_cap_usd
        self.estimated_cost_usd: Decimal = Decimal("0")
        self.actual_cost_usd: Decimal | None = None

    def __enter__(self) -> CostMeter:
        self.estimated_cost_usd = price_for(self._sku, units=self._units)
        spent = ProjectRepo.spend(self._session, self._project_id)
        cap = self._budget_cap_usd
        if cap is None:
            project = ProjectRepo.get(self._session, self._project_id)
            cap = project.budget_cap_usd if project else Decimal(str(PROJECT_BUDGET_USD_DEFAULT))
        if spent + self.estimated_cost_usd > cap:
            raise BudgetExceeded(self._project_id, float(spent), float(cap))

        now = datetime.now(UTC)
        CostRepo.record(
            self._session,
            project_id=self._project_id,
            claim_id=self._claim_id,
            api=self._api,
            sku=self._sku,
            units=self._units,
            cost_usd=self.estimated_cost_usd,
            at=now,
        )
        self._session.flush()
        self._stream_to_bigquery(sku=self._sku, cost_usd=self.estimated_cost_usd, at=now)
        return self

    def _stream_to_bigquery(self, *, sku: str, cost_usd: Decimal, at: datetime) -> None:
        """Best-effort: BigQuery is a derived analytics mirror, never the source of truth
        (packages/ledger/repositories.py's Postgres write above is). A streaming failure
        must not roll back or block the real transaction — log via the caller and move on."""
        if not bq_stream.streaming_enabled():
            return
        try:
            bq_stream.stream_cost_event(
                project_id=self._project_id,
                claim_id=self._claim_id,
                api=self._api,
                sku=sku,
                units=self._units,
                cost_usd=cost_usd,
                at=at,
            )
        except Exception as exc:
            get_logger(__name__).warning(
                "bq_stream_cost_event_failed", project_id=self._project_id, error=str(exc)
            )

    def record_actual(self, actual_cost_usd: Decimal) -> None:
        self.actual_cost_usd = actual_cost_usd
        delta = actual_cost_usd - self.estimated_cost_usd
        if delta != 0:
            CostRepo.record(
                self._session,
                project_id=self._project_id,
                claim_id=self._claim_id,
                api=self._api,
                sku=f"{self._sku}.correction",
                units=1,
                cost_usd=delta,
                at=datetime.now(UTC),
            )
            self._session.flush()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None
