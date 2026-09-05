# Phase 3.6 — dashboard_api evidence

`services/dashboard_api` deployed to Cloud Run (`sa-dashboard-api`, private/IAM-required —
never `--allow-unauthenticated`):

```
$ gcloud run deploy dashboard-api --region=us-central1 \
    --image=us-central1-docker.pkg.dev/ouroboros-507503/ouroboros/dashboard-api:latest \
    --service-account=sa-dashboard-api@ouroboros-507503.iam.gserviceaccount.com \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=...,DB_HOST=10.175.0.3,...,INTAKE_BUCKET=ouroboros-507503-intake-dev" \
    --set-secrets="DB_PASSWORD=DB_PASSWORD:latest" \
    --no-allow-unauthenticated --vpc-connector=ouroboros-dev-conn --vpc-egress=private-ranges-only

Service [dashboard-api] revision [dashboard-api-00001-5sg] has been deployed and is serving 100 percent of traffic.
```

```
$ gcloud run revisions describe dashboard-api-00001-5sg --region=us-central1 --format="value(status.conditions)"
Ready=True; ContainerHealthy=True (in 8.58s); ContainerReady=True; ResourcesAvailable=True
```

## Contract tests — real repository layer, real local Postgres

The three endpoints (`POST/GET /projects/{id}/assets`, `GET /projects/{id}/claims`) run
through the exact same `packages.ledger.repositories`/`session_scope` code already proven
live in `services/ingest` (`docs/evidence/03-ingest.md`) — the same Cloud SQL instance,
the same secret. Only the outbound GCS-signing call is mocked (needs real IAM
credentials `make test` doesn't have); everything else — 404 handling, the naming-
convention validation on upload, category/status filtering — runs for real against
`docker-compose`'s Postgres:

```
$ uv run pytest tests/services/dashboard_api -v
test_healthz PASSED
test_create_upload_url_for_script PASSED
test_create_upload_url_for_cut PASSED
test_create_upload_url_rejects_wrong_extension PASSED
test_create_upload_url_unknown_project_404s PASSED
test_list_assets_unknown_project_404s PASSED
test_list_claims_returns_seeded_claim PASSED
test_list_claims_filters_by_category PASSED
test_openapi_schema_renders PASSED
9 passed
```

`test_openapi_schema_renders` confirms PHASE_03.md §3.6's "OpenAPI docs render"
criterion — `/openapi.json` returns valid schema for both `/projects/{project_id}/assets`
and `/projects/{project_id}/claims`.

## Known gap: live HTTP verification against the deployed URL

Consistent with the limitation already noted in `docs/BLOCKERS.md` (this agent's
sandboxed shell cannot reach `*.run.app` URLs directly — every attempt, via `urllib` and
via `gcloud run services proxy`, returns a generic Google-Frontend 404 rather than the
app's own response), a real authenticated HTTP round-trip against the deployed
`dashboard-api` service was not directly verifiable from this environment. Confidence
instead comes from: the revision's own container health check passing (proves the
FastAPI app object constructs and Uvicorn binds successfully), and the contract tests
above exercising the identical code path (same repositories, same `session_scope`,
same Cloud SQL instance) that `services/ingest` already proved live. If a human with
normal network access curls the service URL with an identity token, that would close
this last gap.
