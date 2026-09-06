# Phase 8.5 — Exports evidence

Three new `packages/exports/*` generators, wired into `services/dashboard_api/main.py`
as `POST /projects/{id}/exports/{eo-pack,factcheck-report,clearance-sheet}`, and a
producer-visible `ExportsPanel` on the project page's Overview tab
(`web/src/components/ExportsPanel.tsx`).

## What's verified

- **Offline, against the real local Postgres schema** (`tests/packages/exports/`):
  `generate_eo_pack` and `generate_factcheck_report` each produce real, valid PDF
  bytes (`%PDF` header, >1KB) from seeded `Project`/`Claim`/`Evidence`/`Risk`/
  `VerificationEvent` rows built through the same repository layer the endpoints use
  — not hand-built fixtures. `export_clearance_sheet`'s row-building and
  create-vs-update idempotency logic is verified with the Sheets/Drive/Firestore
  calls mocked (no real Google Workspace credentials in the offline test env), 4
  tests total plus the pre-existing eo-pdf/factcheck suites: 10 exports-package
  tests, all passing.
- **Full project regression**: `pytest -m "not live"` — 232 passed (up from 219
  before Phase 8.4/8.5), zero regressions. `ruff check`/`ruff format --check`/
  `mypy --strict` clean across every new file (`packages/exports/*`,
  `services/dashboard_api/main.py`).
- **Frontend**: `tsc -b`, `vite build`, and `oxlint` all clean with `ExportsPanel`
  added; no new lint warnings beyond pre-existing ones in unrelated files.
- **Live deployment routing**: after rebuilding and redeploying `dashboard-api`
  (`gcloud builds submit` + `gcloud run deploy`, revision `dashboard-api-00027-gml`),
  all three export endpoints return `422` (missing `Authorization` header) rather
  than `404` when hit unauthenticated — confirms the routes are live on the real
  Cloud Run service, not just present in source.
- **Terraform**: `drive.googleapis.com` added to the enabled-APIs list
  (`infra/main.tf`) — the clearance-sheet export's Drive `permissions.create` call
  needs it — and applied with `-target` scoped to just that one resource
  (`module.project_services.google_project_service.apis["drive.googleapis.com"]`),
  deliberately avoiding an unrelated pre-existing `terraform plan` diff this session
  didn't cause (`module.eventarc.google_project_iam_member.gcs_agent_publishes_for_eventarc`
  wants to be replaced, and two Pub/Sub subscriptions want an in-place update) —
  worth the team's attention separately, not folded into this change.

## What's not verified live, and why

Acceptance calls for generating all three exports against the real deployed `demo`
project and confirming the PDF opens cleanly / the Sheet is populated / the links are
visible in the UI. This session confirmed the code path is correct (above) but could
not complete a fully live, real-data, real-auth run of the three endpoints end to end:

- `get_current_user` requires a Google Identity Services ID token whose `aud` matches
  this project's real OAuth Web-application Client ID and whose `email` is a
  recognized dashboard user (`config/roles.yaml`) — minting one outside an actual
  browser sign-in isn't something a CLI can script headlessly (unlike
  `require_internal_caller`'s service-account identity tokens, which `gcloud auth
  print-identity-token --impersonate-service-account` can produce).
- A local Cloud SQL Auth Proxy connection to the real prod instance
  (`ouroboros-507503:us-central1:ouroboros-dev`) to call the generators directly
  against real `demo` project data hit `password authentication failed for user
  "app"` even with the exact `DB_PASSWORD` Secret Manager value the deployed services
  themselves use (confirmed via `gcloud secrets versions access`) — the same secret
  value that Phase 8.4's `ask_question()` calls prove works for a *direct* private-IP
  connection from the deployed Agent Engine (a real Coca-Cola claim came back
  correctly during that test), so this looks like a proxy-specific auth quirk rather
  than a wrong credential; not investigated further since fixing it isn't this
  session's task and touching prod DB auth config wasn't warranted for a export smoke
  test.

Net effect: the generation logic, the HTTP layer, the deployment, and the frontend
are all verified independently and each is high-confidence; the one gap is an
actual browser-driven click-through with a real signed-in user, which needs a human
(or a browser-automation tool this environment doesn't have) to close.
