"""Streaming insert of cost_events into BigQuery for near-real-time spend visibility.

Opt-in via BQ_STREAM_COST_EVENTS=true — off by default so tests and local dev don't need
BigQuery credentials or a real dataset. The nightly full mirror
(services/dashboard_api/jobs/bq_sync.py) reconciles regardless of whether streaming ran.
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from functools import lru_cache

from google.cloud import bigquery


def streaming_enabled() -> bool:
    return os.environ.get("BQ_STREAM_COST_EVENTS", "false").lower() == "true"


@lru_cache(maxsize=1)
def _client() -> bigquery.Client:
    return bigquery.Client()


def stream_cost_event(
    *,
    project_id: str,
    claim_id: str | None,
    api: str,
    sku: str | None,
    units: int,
    cost_usd: Decimal,
    at: datetime,
) -> None:
    """No-op unless BQ_STREAM_COST_EVENTS=true. Raises on a genuine BigQuery-side failure —
    callers (CostMeter) decide whether that should block the caller's own transaction."""
    if not streaming_enabled():
        return

    gcp_project = os.environ["GOOGLE_CLOUD_PROJECT"]
    table_ref = f"{gcp_project}.ouroboros.cost_events"
    row = {
        "id": None,  # Postgres-only serial; BigQuery's copy is NULLABLE for streamed rows
        "project_id": project_id,
        "claim_id": claim_id,
        "api": api,
        "sku": sku,
        "units": units,
        "cost_usd": str(cost_usd),
        "at": at.isoformat(),
    }
    errors = _client().insert_rows_json(table_ref, [row])
    if errors:
        raise RuntimeError(f"BigQuery streaming insert failed: {errors}")
