# PARALLEL_API_KEY's container is imported (created manually via gcloud before this
# module existed, 2026-09-03) — Terraform manages the container only; the human
# supplies the value out of band. See infra/README.md for the import command.
resource "google_secret_manager_secret" "parallel_api_key" {
  project   = var.project_id
  secret_id = "PARALLEL_API_KEY"

  replication {
    auto {}
  }
}

resource "random_password" "db_password" {
  length  = 32
  special = false # Cloud SQL private-IP connections don't need shell-unsafe characters.
}

resource "google_secret_manager_secret" "db_password" {
  project   = var.project_id
  secret_id = "DB_PASSWORD"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

# Placeholders — containers only, no version. Populated by hand in Phase 7 (webhook
# secret, once the Parallel webhook is registered) and Phase 7.4 (Slack webhook URL).
resource "google_secret_manager_secret" "parallel_webhook_secret" {
  project   = var.project_id
  secret_id = "PARALLEL_WEBHOOK_SECRET"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "slack_webhook_url" {
  project   = var.project_id
  secret_id = "SLACK_WEBHOOK_URL"

  replication {
    auto {}
  }
}
