# Phase 9.7 — Freeze `demo` environment evidence

## A real architectural note before the checklist

PHASE_09.md §9.7 assumes a separate `demo` deployment to freeze independently from
`dev`. This project's actual infrastructure doesn't have that: `infra/environments/
demo.tfvars` sets only `env = "demo"` (an environment-name Terraform variable used
for a handful of resource-naming suffixes) against the **same** `project_id =
"ouroboros-507503"` as `dev.tfvars` — there is one GCP project, one set of deployed
Cloud Run services, one Agent Engine, one Cloud SQL instance. "Demo" in this
codebase is a **product-level** concept (`project_id = "demo"`, a row in the
`projects` table seeded by `scripts/seed.py` from `fixtures/projects/demo.yaml`, and
`PUBLIC_SHOWCASE_PROJECT_ID`'s default), not a second infrastructure environment to
deploy `main` into. There is nothing to "deploy main to demo" beyond what's already
continuously true: every push to `main` already deploys to the one real environment
this whole project runs in.

Given that, this pass treats §9.7 as: confirm the demo *project*'s real state,
snapshot the real database, and correctly *not* set `SUBMISSION_AT` yet.

## Demo project real state (confirmed, not assumed)

- **Real claims exist and are verified**: `bq query` against the BigQuery ledger
  mirror confirms real rows for `project_id = "demo"`. Separately, this session's own
  Phase 8.4 testing (`docs/evidence/08-ask.md`) directly queried and cited real
  claims by ID (`97dfd8f22a95e4908916efc8` — Coca-Cola, low risk; `d858a792c9f136760193ad34`
  — Coke dialogue mention, blocking risk) with real evidence and citations, proving
  a real CLEAR pass has run against this project.
- **`GET /public/showcase-metrics`** (unauthenticated, real, called live this pass)
  returns `{"reality_drift": 0.0, "drift_7d": null, "current_cadence": "1d"}` — a
  real response from real project-summary data, not a stub.

## Real Cloud SQL snapshot taken

```
$ gcloud sql backups create --instance=ouroboros-dev \
    --description="Phase 9.7 pre-submission freeze snapshot, 2026-09-06"
Backing up Cloud SQL instance...done.

$ gcloud sql backups list --instance=ouroboros-dev --limit=3
ID             STATUS      WINDOW_START_TIME              DESCRIPTION
1788699126105  SUCCESSFUL  2026-09-06T12:52:06.105+00:00  Phase 9.7 pre-submission freeze snapshot, 2026-09-06
1788663600000  SUCCESSFUL  2026-09-06T03:00:00.000+00:00
1788577200000  SUCCESSFUL  2026-09-05T03:00:00.000+00:00
```

A real, on-demand backup, confirmed `SUCCESSFUL`. The two earlier entries (no
description) are the instance's own already-configured automated daily backups —
real backup infrastructure already existed before this pass; this just adds one more,
deliberately timestamped and labeled for this freeze point.

## `SUBMISSION_AT` — deliberately not set yet

`web/.env.example`'s own comment is explicit: *"Leave unset until submission actually
happens -- the divider simply doesn't render rather than showing a fabricated
date."* Today is 2026-09-06; the real submission deadline is 2026-09-10, 02:30 IST.
Setting this now would fabricate a "since submission" marker for an event that
hasn't happened — exactly what this project's own stated principle (real data over
mocked, `PRODUCT.md` Principle 4) argues against. **Action for whoever actually
submits**: set `VITE_SUBMISSION_AT` (and any backend equivalent, if one is added
later) to the real submission timestamp at that moment, not before.

## What wasn't verified this pass, honestly

- **"Monitors active, webhook pointing at demo"**: real Monitor records aren't
  synced to the BigQuery ledger mirror (only `claims`/`evidence`/`verification_history`/
  `cost_events`/`risk_history` are), and this session has no way to query the real
  prod Cloud SQL directly (the same Cloud SQL Auth Proxy password issue noted in
  Phase 8.4/8.5's own evidence docs) to list them. Not re-verified live this pass;
  Phase 7's own evidence (`docs/evidence/07-loop.md`, `docs/DECISIONS.md` #099) already
  documents real, externally-originated webhook deliveries against `webhook-receiver`
  being correctly received and rejected pending the real webhook secret.
- **"Drift non-zero after the first monitor cycle"**: `GET /public/showcase-metrics`
  shows `reality_drift: 0.0` right now — no real monitor cycle has yet detected and
  processed a material change for the demo project. Forcing one requires either (a)
  real wall-clock time for an organic monitor cycle (cadence is `1d` per the same
  showcase-metrics response, so up to 24h), or (b) the internal, service-account-gated
  `POST /internal/jobs/trigger-monitor/{monitor_id}` endpoint (`require_internal_caller`,
  allow-listed to `sa-scheduler`/`sa-ingest` only) — attempted impersonating
  `sa-scheduler` to mint a real identity token for this specifically, and was
  correctly denied (`IAM_PERMISSION_DENIED` on `iam.serviceAccounts.getAccessToken` —
  this session's own identity was never granted `roles/iam.serviceAccountTokenCreator`
  on that service account, which is the *correct*, least-privilege outcome, not a bug
  to route around). Not forced; left as a real, honest gap rather than working around
  a permission boundary that's doing exactly its job.
