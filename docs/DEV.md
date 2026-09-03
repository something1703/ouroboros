# Local development

## Prerequisites

- Python — handled automatically by `uv` (pins 3.12; run `uv python install 3.12` if you want it cached ahead of time).
- [`uv`](https://docs.astral.sh/uv/) — package manager for everything under `pyproject.toml`.
- Docker Desktop (or another Docker-compatible daemon) — for `docker compose`.
- `gcloud` CLI, authenticated: `gcloud auth login && gcloud auth application-default login`.
- Access to the `ouroboros-507503` GCP project (ask for IAM access if you don't have it).

## First-time setup

```
git clone https://github.com/something1703/ouroboros.git
cd ouroboros
cp .env.example .env   # fill in PARALLEL_API_KEY at minimum; ask a teammate or check Secret Manager
make setup              # uv sync, pre-commit install, gcloud sanity check
make lint
make test
```

Should take under 15 minutes on a machine with `uv`, `docker`, and `gcloud` already installed.

## Running things locally

```
make run-local
```

Today (Phase 1) this only brings up `postgres` — the rest of `docker-compose.yml` is
commented out because `services/ingest`, `services/dashboard_api`, `services/toolbox`,
and `web` don't have application code yet. Uncomment each block as its phase lands:

| Service | Lands in | Depends on |
|---|---|---|
| `postgres` | Phase 1 (works now) | — |
| `toolbox` | Phase 2.3 | `services/toolbox/tools.yaml` |
| `ingest` | Phase 3 | `services/ingest/Dockerfile` |
| `dashboard_api` | Phase 3 (thin), 5, 8 (full) | `services/dashboard_api/Dockerfile` |
| `web` | Phase 8 | a real Vite app in `web/` |

To bring up just Postgres and poke at it directly:

```
docker compose up -d postgres
psql postgresql://app:localdev@localhost:5432/ouroboros   # pragma: allowlist secret — local-only placeholder
docker compose down
```

## Running the test suite

```
make test        # offline — recorded vcrpy cassettes only, no network, this is what CI runs
make test-live    # hits real APIs — needs .env populated with real keys, never runs in CI
```

## Verifying a claim by hand (once Phase 4 lands)

```
make seed
uv run python scripts/verify_claim.py --claim-id <id> --dry-run
```

## Deploying

```
make deploy ENV=dev    # terraform apply + cloud run deploy + agent engine deploy
```

Terraform state lives in `gs://ouroboros-507503-tfstate`; you need `roles/owner` or
equivalent on `ouroboros-507503` to apply. See `infra/README.md` for what gets created.
