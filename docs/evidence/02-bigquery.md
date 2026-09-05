# Phase 2.5 — BigQuery mirror evidence

`terraform apply`: dataset `ouroboros` + 5 day-partitioned tables + the
`claims_for_enrichment` view (Phase 7.5). Confirmed real:

```
$ bq ls --project_id=ouroboros-507503 ouroboros
claims                  TABLE   DAY (field: created_at)
claims_for_enrichment   VIEW
cost_events             TABLE   DAY (field: at)
evidence                TABLE   DAY (field: created_at)
risk_history            TABLE   DAY (field: assessed_at)
verification_history    TABLE   DAY (field: at)
```

## Full mirror job, run for real (not a dry run)

Created a real claim + evidence + verification_history row + cost_events row in local
Postgres, then ran `services/dashboard_api/jobs/bq_sync.py` against the real BigQuery
dataset:

```
$ uv run python -m services.dashboard_api.jobs.bq_sync --project ouroboros-507503
synced 1 rows -> ouroboros.claims
synced 1 rows -> ouroboros.evidence
synced 0 rows -> ouroboros.risk_history
synced 1 rows -> ouroboros.cost_events
synced 1 rows -> ouroboros.verification_history
```

Verified with a real query, not just the row count:
```
$ bq query --use_legacy_sql=false "SELECT claim_id, entity_text, category, status FROM ouroboros.claims"
0f9297ef05b78d6458968fe1 | Coca-Cola | brand | verified
```

**Bug 1, found and fixed**: the first run failed —
`400 Unsupported empty struct type for field 'ref'`. BigQuery's JSON-from-NDJSON loader
can't handle an empty dict (`{}`) for a `JSON`-typed column, even though the destination
column's type is already fixed by the existing table schema. Fixed in `bq_sync.py`:
`_json_safe` now maps an empty dict to `null` before upload (semantically equivalent for
our data — an empty `ref`/`territory_flags` object and a null one mean the same thing).

**Bug 2, more serious, found and fixed**: after that first successful run, `terraform
plan` started showing `evidence` and `verification_history` as needing full replacement
— their `JSON`-typed columns (`output`, `basis`, `ref`) had turned into nested `RECORD`
types in the *real* BigQuery schema. Root cause: `bq_sync.py`'s `LoadJobConfig` set
`write_disposition`/`source_format` but no explicit `schema`, and no `autodetect=False`
— so the load job inferred each JSON column's shape from that run's actual data
(`{"brand_owner": "..."}`) and silently rewrote the live table schema to match, out from
under Terraform. Fixed by fetching the destination table's existing schema
(`bq_client.get_table(table_ref).schema`) and passing it explicitly into `LoadJobConfig`
— this is what actually stops a load job from ever inferring or rewriting a schema.
Restored the two tables via `terraform apply` (recreated them, losing only my own test
rows), reran the sync with the fix, and confirmed `terraform plan` now shows no diff.
See `docs/DECISIONS.md` #023.

## Streaming path, also run for real

`packages/parallel_client/cost.py`'s `CostMeter` calls
`packages/ledger/bq_stream.stream_cost_event` on every metered call, gated by
`BQ_STREAM_COST_EVENTS=true` (off by default — tests and normal local dev don't need
BigQuery credentials). Verified with the flag on:

```
$ BQ_STREAM_COST_EVENTS=true uv run python -c "... CostMeter(session, 'demo', api='search', sku='search.fast', ...) ..."
$ bq query --use_legacy_sql=false "SELECT project_id, api, sku, cost_usd FROM ouroboros.cost_events ORDER BY \`at\`"
demo | task   | task.core-fast | 0.025   <- from the batch sync
demo | search | search.fast    | 0.001   <- from the live stream, same run
```

Both rows present confirms the streaming insert landed independently of the batch job.

## Gotcha for later

`at` (the timestamp column name, kept identical to the Postgres schema) is a reserved
word in BigQuery Standard SQL — any query against `cost_events` or
`verification_history` needs to backtick-quote it (`` ORDER BY `at` ``), discovered when
the first un-quoted query above failed with a syntax error. Noted in
`infra/modules/bigquery/main.tf`.
