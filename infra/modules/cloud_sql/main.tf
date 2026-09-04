resource "google_sql_database_instance" "ouroboros" {
  project             = var.project_id
  name                = "ouroboros-${var.env}"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection

  settings {
    # ENTERPRISE_PLUS (the current GCP default edition) only allows
    # db-perf-optimized-* tiers; db-f1-micro requires the legacy ENTERPRISE
    # edition. Explicit here since the first live apply failed without it.
    edition           = "ENTERPRISE"
    tier              = "db-f1-micro" # smallest tier — hackathon demo scale, per PHASE_02.md §2.2
    availability_type = "ZONAL"
    disk_size         = 10
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = false
      start_time                     = "03:00"
    }

    ip_configuration {
      ipv4_enabled    = var.enable_public_ip # see variables.tf — off by default
      private_network = var.vpc_network_id
    }

    # db-f1-micro's auto-calculated default (25, from its 0.6GB RAM) isn't enough once
    # every service sharing this instance (agents/ouroboros's own direct budget/cost
    # tracking, Toolbox's separate pool for every ledger read/write, dashboard-api,
    # ingest) is counted together — found live running a real CLEAR pass at demo scale
    # (docs/DECISIONS.md #055, #060, #061): even after tuning every consumer's own pool
    # size down, connection timeouts kept accumulating under real concurrent load.
    # Applied manually first (`gcloud sql instances patch`, verified live) then codified
    # here so a future `terraform apply` doesn't drift it back to the tier default.
    database_flags {
      name  = "max_connections"
      value = "100"
    }
  }

  depends_on = [var.private_service_connection]
}

resource "google_sql_database" "ouroboros" {
  project  = var.project_id
  instance = google_sql_database_instance.ouroboros.name
  name     = "ouroboros"
}

resource "google_sql_user" "app" {
  project  = var.project_id
  instance = google_sql_database_instance.ouroboros.name
  name     = "app"
  password = var.db_password
}
