#!/usr/bin/env python3
"""Nightly full mirror: Cloud SQL -> BigQuery.

Runnable standalone today (`uv run python -m services.dashboard_api.jobs.bq_sync`);
TODO (Phase 3+) wire behind Cloud Scheduler -> a Cloud Run job once
services/dashboard_api is itself a deployed service, per PHASE_02.md §2.5.

Full mirror, not incremental — the ledger tables are small at hackathon scale, so
truncate-and-reload each table is the simplest correct approach. cost_events also gets a
streaming path (packages.ledger.bq_stream.stream_cost_event, called from
packages.parallel_client.cost.CostMeter) for near-real-time spend visibility; this job is
the nightly reconciling full-refresh for every table regardless of whether streaming ran.
"""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime
from decimal import Decimal

from google.cloud import bigquery
from sqlalchemy import text

from packages.ledger.db import get_engine

_TABLES: list[str] = ["claims", "evidence", "risk_history", "cost_events", "verification_history"]


def _json_safe(value: object) -> object:
    """BigQuery's JSON load path wants plain JSON-compatible values: Decimal and
    datetime/date need converting, everything else (str, int, bool, dict, list, None)
    passes through as-is — including JSONB columns, which psycopg already hands back
    as native dict/list. One real exception found by running this against BigQuery:
    an empty dict for a JSON-typed column fails the load with "Unsupported empty
    struct type" — semantically equivalent to null for our data, so map it there."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict) and not value:
        return None
    return value


def _row_to_json(row: dict[str, object]) -> dict[str, object]:
    return {key: _json_safe(value) for key, value in row.items()}


def sync_table(bq_client: bigquery.Client, project_id: str, table_name: str) -> int:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table_name}"))
        rows = [_row_to_json(dict(row._mapping)) for row in result]

    if not rows:
        return 0

    table_ref = f"{project_id}.ouroboros.{table_name}"
    # schema_update_options=[] (the default) is not enough on its own to stop drift: a
    # load job with neither an explicit `schema` nor `autodetect=False` can still infer
    # a JSON-typed column's shape from the data and silently rewrite it to a nested
    # RECORD — caught live when this turned evidence.output/basis and
    # verification_history.ref from JSON into RECORD, which Terraform then flagged as
    # wanting to replace those tables (see docs/DECISIONS.md #023, docs/evidence/02-bigquery.md).
    # Pinning the existing table's schema explicitly is what actually prevents it.
    table = bq_client.get_table(table_ref)
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=table.schema,
        autodetect=False,
    )
    load_job = bq_client.load_table_from_json(rows, table_ref, job_config=job_config)
    load_job.result()  # raises on failure
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    args = parser.parse_args()
    if not args.project:
        parser.error("--project or GOOGLE_CLOUD_PROJECT is required")

    bq_client = bigquery.Client(project=args.project)
    for table in _TABLES:
        count = sync_table(bq_client, args.project, table)
        print(f"synced {count} rows -> ouroboros.{table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
