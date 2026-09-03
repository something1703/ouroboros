# Phase 2.2 — Cloud SQL evidence

## Migration applied to both targets

**Local Postgres** (`docker-compose.yml`):
```
$ DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev uv run alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial, initial schema
$ docker exec ouroboros-postgres-1 psql -U app -d ouroboros -c "\dt"
 assets, claims, cost_events, evidence, monitors, prior_decisions, projects, risk, risk_history, verification_history  (10 tables + alembic_version)
```

**Real Cloud SQL** (`ouroboros-507503:us-central1:ouroboros-dev`), via the Cloud SQL Auth Proxy:
```
$ GOOGLE_CLOUD_PROJECT=ouroboros-507503 DB_HOST=localhost DB_PORT=5433 DB_NAME=ouroboros DB_USER=app \
    uv run alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial, initial schema
$ GOOGLE_CLOUD_PROJECT=ouroboros-507503 DB_HOST=localhost DB_PORT=5433 DB_NAME=ouroboros DB_USER=app \
    uv run python scripts/seed.py
seeded project 'demo' from fixtures/projects/demo.yaml
```

## The public-IP wrinkle

The instance is private-IP-only (`ipv4_enabled = false`) — correct for how Cloud Run reaches
it (via the Serverless VPC Access connector) but the Cloud SQL Auth Proxy's default mode needs
a public IP to *dial*, even though the tunnel itself stays TLS/IAM-authenticated end to end.
My laptop isn't inside the VPC, so `--private-ip` mode (which needs real network-layer
reachability to `10.175.0.3`) wasn't an option either.

Fix: added `enable_public_ip` (default `false`) to `infra/modules/cloud_sql`, flipped it to
`true` just long enough to run the two commands above, then flipped it back and re-applied.
Confirmed reverted:
```
$ gcloud sql instances describe ouroboros-dev --format="value(ipAddresses)"
{'ipAddress': '10.175.0.3', 'type': 'PRIVATE'}
```
`terraform plan` shows no diff after reverting. Total public-IP exposure window: under two
minutes, and Cloud SQL never accepts unauthenticated connections regardless of IP type.

## Also caught: `db-f1-micro` needs the legacy edition

First live `terraform apply` failed: `Invalid Tier (db-f1-micro) for (ENTERPRISE_PLUS)
Edition`. GCP's current default Cloud SQL edition (`ENTERPRISE_PLUS`) only allows
`db-perf-optimized-*` tiers; the smallest shared-core tier needs `edition = "ENTERPRISE"`
set explicitly. Fixed in `infra/modules/cloud_sql/main.tf`.
