locals {
  # AGENTS.md §3 / PHASE_01.md §1.2, plus the base APIs every module below needs.
  apis = [
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "sql-component.googleapis.com",
    "firestore.googleapis.com",
    "pubsub.googleapis.com",
    "eventarc.googleapis.com",
    "secretmanager.googleapis.com",
    "bigquery.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "iap.googleapis.com",
    "discoveryengine.googleapis.com",
    "modelarmor.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    # No longer used: the clearance-log export was a Google Sheet until it turned out
    # a bare service account has no Drive storage quota and can never own a file it
    # creates (a real 403, see docs/DECISIONS.md) -- it writes a CSV to GCS now.
    # Left enabled rather than removed: disabling an API is a destroy operation, and
    # these cost nothing while idle. Safe to drop in a later, non-demo-adjacent pass.
    "sheets.googleapis.com",
    "drive.googleapis.com",
    # PHASE_09.md §9.3: deploys infra/firestore.rules (google_firebaserules_ruleset/
    # _release below) -- Firestore security rules are a Firebase Rules API resource.
    "firebaserules.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
  ]
}

module "project_services" {
  source     = "./modules/project_services"
  project_id = var.project_id
  apis       = local.apis
}

module "network" {
  source     = "./modules/network"
  project_id = var.project_id
  region     = var.region
  env        = var.env

  depends_on = [module.project_services]
}

module "artifact_registry" {
  source     = "./modules/artifact_registry"
  project_id = var.project_id
  region     = var.region

  depends_on = [module.project_services]
}

module "storage" {
  source     = "./modules/storage"
  project_id = var.project_id
  region     = var.region
  env        = var.env
  # Matches CORS_ALLOWED_ORIGINS on dashboard-api (.github/workflows/deploy.yml) --
  # the same two origins that need to reach the API also need to reach GCS directly.
  cors_origins = ["http://localhost:5173", "https://web-492372502792.us-central1.run.app"]

  depends_on = [module.project_services]
}

module "iam" {
  source     = "./modules/iam"
  project_id = var.project_id

  depends_on = [module.project_services]
}

module "secrets" {
  source     = "./modules/secrets"
  project_id = var.project_id

  depends_on = [module.project_services]
}

module "cloud_sql" {
  source                     = "./modules/cloud_sql"
  project_id                 = var.project_id
  region                     = var.region
  env                        = var.env
  vpc_network_id             = module.network.network_id
  private_service_connection = module.network.private_service_connection
  db_password                = module.secrets.db_password

  depends_on = [module.network, module.secrets]
}

module "bigquery" {
  source     = "./modules/bigquery"
  project_id = var.project_id
  region     = var.region

  depends_on = [module.project_services]
}

module "model_armor" {
  source     = "./modules/model_armor"
  project_id = var.project_id
  region     = var.region

  depends_on = [module.project_services]
}

# AskOuroboros's private corpus (PHASE_08.md §8.4) -- documents ingested separately via
# scripts/ingest_private_corpus.py once the datastore exists.
module "vertex_search" {
  source     = "./modules/vertex_search"
  project_id = var.project_id

  depends_on = [module.project_services]
}

module "pubsub" {
  source             = "./modules/pubsub"
  project_id         = var.project_id
  region             = var.region
  sa_scheduler_email = module.iam.service_account_emails["sa-scheduler"]

  depends_on = [module.project_services, module.iam]
}

# Needs dashboard-api to already exist (deploy.yml's deploy-services runs before
# terraform-apply, same ordering constraint as pubsub/eventarc above).
module "scheduler" {
  source             = "./modules/scheduler"
  project_id         = var.project_id
  region             = var.region
  sa_scheduler_email = module.iam.service_account_emails["sa-scheduler"]

  depends_on = [module.project_services, module.iam]
}

module "monitoring" {
  source             = "./modules/monitoring"
  project_id         = var.project_id
  notification_email = "rvsrathore17@gmail.com"

  depends_on = [module.project_services]
}

# See infra/modules/eventarc/main.tf's header comment: this needs the `ingest` Cloud Run
# service to already exist, which deploy.yml guarantees by deploying services before
# running `terraform apply`.
module "eventarc" {
  source                       = "./modules/eventarc"
  project_id                   = var.project_id
  region                       = var.region
  intake_bucket                = module.storage.intake_bucket
  ingest_service_account_email = module.iam.service_account_emails["sa-ingest"]

  depends_on = [module.storage, module.iam]
}

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [module.project_services]
}

# PHASE_09.md §9.3: deny-all client rules -- every real reader/writer here is a
# backend service account (roles/datastore.user), never a browser/mobile client.
resource "google_firebaserules_ruleset" "firestore_deny_all" {
  provider = google-beta
  project  = var.project_id

  source {
    files {
      name    = "firestore.rules"
      content = file("${path.module}/firestore.rules")
    }
  }

  depends_on = [google_firestore_database.default]
}

resource "google_firebaserules_release" "firestore_deny_all" {
  provider     = google-beta
  project      = var.project_id
  name         = "cloud.firestore"
  ruleset_name = "projects/${var.project_id}/rulesets/${google_firebaserules_ruleset.firestore_deny_all.name}"
}

# services/toolbox (Cloud Run, private) is deployed via gcloud in deploy.yml, same
# ordering constraint as infra/modules/eventarc — this needs the service to already
# exist. Three callers are granted invoke here, no others: ADK agents at runtime
# (sa-agent-engine, via packages/ledger/toolbox_client.py's ID-token auth), the public
# read-only proxy (sa-toolbox-public, Phase 5.6), and CI's own deploy step (sa-ci-deploy,
# which constructs `root_agent` locally to build/upload it to Agent Engine — that
# construction loads live Toolbox tool schemas the same way any ADK agent build does). A
# human's own Owner role already covers ad-hoc/local invocation.
resource "google_cloud_run_v2_service_iam_member" "toolbox_invoker_agent_engine" {
  project  = var.project_id
  location = var.region
  name     = "toolbox"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.iam.service_account_emails["sa-agent-engine"]}"
}

# services/toolbox_public (Phase 5.6, also gcloud-deployed) — the public-facing proxy
# Parallel Task runs call back into; ledger_write is never exposed through it
# (services/toolbox_public only ever requests the parallel_readonly toolset).
resource "google_cloud_run_v2_service_iam_member" "toolbox_invoker_toolbox_public" {
  project  = var.project_id
  location = var.region
  name     = "toolbox"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.iam.service_account_emails["sa-toolbox-public"]}"
}

resource "google_cloud_run_v2_service_iam_member" "toolbox_invoker_ci_deploy" {
  project  = var.project_id
  location = var.region
  name     = "toolbox"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.iam.service_account_emails["sa-ci-deploy"]}"
}
