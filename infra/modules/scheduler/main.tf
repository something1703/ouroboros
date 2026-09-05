# Phase 7.3 (PHASE_07.md §7.3): daily coil-tightening — cadence increases as each
# project's release date approaches, and every active Monitor's webhook URL is
# reconciled to whichever service currently owns `/webhooks/parallel/*`
# (docs/DECISIONS.md #095).

data "google_cloud_run_v2_service" "dashboard_api" {
  project  = var.project_id
  location = var.region
  name     = var.dashboard_api_service_name
}

resource "google_cloud_scheduler_job" "tighten_monitors" {
  project   = var.project_id
  region    = var.region
  name      = "tighten-monitors"
  schedule  = "0 6 * * *" # daily 06:00 IST
  time_zone = "Asia/Kolkata"

  http_target {
    http_method = "POST"
    uri         = "${data.google_cloud_run_v2_service.dashboard_api.uri}/internal/jobs/tighten"

    oidc_token {
      service_account_email = var.sa_scheduler_email
      audience              = data.google_cloud_run_v2_service.dashboard_api.uri
    }
  }
}
