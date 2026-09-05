"""Shared budget-check/cost-recording helpers, Toolbox-routed (docs/DECISIONS.md #062:
the deployed Agent Engine's runtime has no VPC path to Cloud SQL's private IP, so a
direct DB connection from the agent process hangs forever). Used by both CLEAR's
`clear/specialist.py` and TRUE CUT's `truecut/fact.py`/`truecut/archive.py` — every
per-claim verification loop needs the exact same pre-flight budget check and per-call
cost reservation, regardless of which head it's verifying for.
"""

from __future__ import annotations

import json
from decimal import Decimal

from agents.ouroboros.tools import ledger
from packages.common.errors import BudgetExceeded
from packages.parallel_client.cost import price_for


def check_budget(project_id: str) -> None:
    """Raises `BudgetExceeded` if the project is *already* over its cap."""
    row = json.loads(ledger.check_budget(project_id=project_id))
    if Decimal(str(row["spend_usd"])) > Decimal(str(row["cap_usd"])):
        raise BudgetExceeded(project_id, float(row["spend_usd"]), float(row["cap_usd"]))


def check_and_record_cost(
    project_id: str, claim_id: str, *, api: str, sku: str, units: int = 1
) -> Decimal:
    """Pre-flight budget check + cost reservation for one priced Parallel call. `units`
    matters for a per-unit SKU (e.g. `extract.per_url`, one unit per URL sent) —
    defaults to 1 for every flat-rate SKU (`search.fast`, `task.core-fast`, ...). Skips
    `packages.parallel_client.cost.CostMeter`'s BigQuery streaming and post-hoc
    `record_actual` correction: a best-effort analytics mirror, not needed for the
    budget-enforcement behavior this replaces (see docs/DECISIONS.md #062)."""
    estimated_cost = price_for(sku, units=units)
    row = json.loads(ledger.check_budget(project_id=project_id))
    spend = Decimal(str(row["spend_usd"]))
    cap = Decimal(str(row["cap_usd"]))
    if spend + estimated_cost > cap:
        raise BudgetExceeded(project_id, float(spend), float(cap))
    ledger.record_cost(
        project_id=project_id,
        claim_id=claim_id,
        api=api,
        sku=sku,
        units=units,
        cost_usd=float(estimated_cost),
    )
    return estimated_cost
