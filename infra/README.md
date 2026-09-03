# infra — Terraform

One GCP project (`ouroboros-507503`), two envs by suffix (`dev`, `demo`), same modules, different `tfvars`. Remote state: `gs://ouroboros-507503-tfstate/terraform/state`.

```
terraform init
terraform plan  -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars
```

## Modules

| Module | Creates |
|---|---|
| `project_services` | Enables the 27 APIs every other module needs (Vertex AI, Cloud Run, Cloud SQL, Firestore, Pub/Sub, Eventarc, Secret Manager, BigQuery, Cloud Scheduler, Cloud Build, Artifact Registry, IAP, Vertex AI Search, Model Armor, Sheets, VPC Access, Service Networking, ...). |
| `network` | Custom VPC (`ouroboros-{env}`), one subnet, a Private Service Access peering range + connection (Cloud SQL private IP, Phase 2), a Serverless VPC Access connector (2× `e2-micro`, smallest supported footprint), and an internal-only firewall rule. |
| `artifact_registry` | One Docker repo, `ouroboros`, shared across envs by region. |
| `storage` | Three GCS buckets — see naming note below. |
| `iam` | 8 service accounts (least privilege, table below) + GitHub Actions Workload Identity Federation for `sa-ci-deploy` (no JSON keys). |
| `secrets` | Secret Manager containers: `PARALLEL_API_KEY` (imported — see below), `DB_PASSWORD` (generated), `PARALLEL_WEBHOOK_SECRET` / `SLACK_WEBHOOK_URL` (placeholders, populated by hand in later phases). |
| (root) | Firestore database, Native mode, region `us-central1`. |

## Bucket naming — deviation from the plan

`DATA_MODEL.md`/`ARCHITECTURE.md` name buckets `ouroboros-intake-{env}` etc. GCS bucket names are global across *all* of Google Cloud, not just this project, so a name that generic risks collision. Buckets are actually named `{project_id}-intake-{env}`, `{project_id}-artifacts-{env}`, `{project_id}-fixtures` (shared, not per-env). See `docs/DECISIONS.md`.

| Bucket | Purpose | Versioning |
|---|---|---|
| `ouroboros-507503-intake-dev` | Landing zone for uploaded scripts/cuts (Eventarc trigger, Phase 3) | On |
| `ouroboros-507503-artifacts-dev` | Exports, proxy video, generated assets | Off |
| `ouroboros-507503-fixtures` | Large sample files (shared across dev/demo) | Off |

## Service accounts and roles

| Service account | Roles | Used by |
|---|---|---|
| `sa-ingest` | `storage.objectViewer`, `aiplatform.user`, `secretmanager.secretAccessor`, `pubsub.publisher`, `datastore.user`, `cloudsql.client`, `logging.logWriter`, `cloudtrace.agent` | `services/ingest` (Phase 3) |
| `sa-webhook` | `pubsub.publisher`, `secretmanager.secretAccessor`, `logging.logWriter`, `cloudtrace.agent` | `services/webhook_receiver` (Phase 7) |
| `sa-reverify` | `aiplatform.user`, `secretmanager.secretAccessor`, `datastore.user`, `pubsub.publisher`, `pubsub.subscriber`, `cloudsql.client`, `logging.logWriter`, `cloudtrace.agent` | `services/reverify_worker` (Phase 7) |
| `sa-dashboard-api` | `datastore.user`, `secretmanager.secretAccessor`, `aiplatform.user`, `cloudsql.client`, `bigquery.dataEditor`, `bigquery.jobUser`, `pubsub.publisher`, `logging.logWriter`, `cloudtrace.agent` | `services/dashboard_api` (Phases 3, 5, 8) |
| `sa-toolbox` | `cloudsql.client`, `logging.logWriter`, `cloudtrace.agent` | `services/toolbox` (Phase 2.3) |
| `sa-agent-engine` | `aiplatform.user`, `secretmanager.secretAccessor`, `datastore.user`, `pubsub.publisher`, `cloudsql.client`, `logging.logWriter`, `cloudtrace.agent` | `agents/ouroboros` deployed to Agent Engine (Phase 5.5) |
| `sa-scheduler` | `run.invoker`, `logging.logWriter` | Cloud Scheduler jobs calling internal endpoints (Phase 7.3) |
| `sa-ci-deploy` | `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser`, `cloudbuild.builds.editor`, `aiplatform.user`, `storage.admin`, `serviceusage.serviceUsageConsumer` | GitHub Actions, via Workload Identity Federation — no long-lived key. Named `sa-ci-deploy` not `sa-ci`: GCP requires service-account IDs ≥ 6 characters. |

**Note:** roles above are granted at the *project* level for hackathon-timeline simplicity, not scoped per-resource (e.g. `secretmanager.secretAccessor` grants read on every secret, not just the ones each service needs). Tighten with per-secret IAM bindings (`google_secret_manager_secret_iam_member`) if this goes past the hackathon.

### Workload Identity Federation (CI)

Pool `github-pool` / provider `github-provider`, OIDC issuer `https://token.actions.githubusercontent.com`, restricted by `attribute_condition` to `assertion.repository == "something1703/ouroboros"` — only workflow runs from that exact repo can impersonate `sa-ci-deploy`. GitHub Actions workflow config: see `.github/workflows/ci.yml` (`google-github-actions/auth` with `workload_identity_provider` = the `ci_workload_identity_provider` output).

## Secrets

`PARALLEL_API_KEY`'s container was created manually via `gcloud secrets create` on 2026-09-03 (before this module existed) and then adopted into state:

```
terraform import -var-file=environments/dev.tfvars \
  'module.secrets.google_secret_manager_secret.parallel_api_key' \
  'projects/ouroboros-507503/secrets/PARALLEL_API_KEY'
```

Terraform manages the container only — the key *value* was set out of band and Terraform will never see or overwrite it (no `google_secret_manager_secret_version` resource for this secret).

`DB_PASSWORD` is fully Terraform-managed: `random_password` generates it, a `google_secret_manager_secret_version` stores it. Cloud SQL (Phase 2.2) reads it to set the `app` user's password.

`PARALLEL_WEBHOOK_SECRET` and `SLACK_WEBHOOK_URL` are containers only (no version yet) — populated by hand in Phase 7.

## Known cost-bearing resources

The Serverless VPC Access connector runs 2× `e2-micro` continuously (~$0.01/hr each while it exists) — the only resource here with a non-negligible idle cost. Everything else in this module is either free-tier or pay-per-request. Run `terraform destroy -target=module.network.google_vpc_access_connector.connector -var-file=environments/dev.tfvars` if you need to pause spend between sessions (Cloud Run services in later phases will need it re-created before they can reach Cloud SQL's private IP).
