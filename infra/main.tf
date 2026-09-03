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
    "sheets.googleapis.com",
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

module "pubsub" {
  source     = "./modules/pubsub"
  project_id = var.project_id

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
