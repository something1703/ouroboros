# Phase 3.1 (PHASE_03.md §3.1): GCS `object.finalized` on the intake bucket -> Cloud Run
# `ingest`, internal-only, invoked by sa-ingest as the trigger's own identity.
#
# Ordering constraint (docs/DECISIONS.md): a trigger's `destination.cloud_run_service`
# and the IAM binding below both require the `ingest` Cloud Run service to already
# exist — `.github/workflows/deploy.yml` deploys services *before* running
# `terraform apply` for exactly this reason.

data "google_storage_project_service_account" "gcs" {
  project = var.project_id
}

# GCS's own service agent needs this to publish into Eventarc's internal transport
# topic for a direct Cloud Storage trigger — separate from anything in the pubsub
# module, and required even though nothing here references a Pub/Sub topic directly.
resource "google_project_iam_member" "gcs_agent_publishes_for_eventarc" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
}

# Found live (docs/DECISIONS.md): trigger creation itself failed with a 403 on
# `storage.buckets.get`, distinct from the GCS-agent grant above — Eventarc's own
# service agent reads the bucket's metadata to validate it exists as part of creating
# the trigger, and `roles/eventarc.serviceAgent` (auto-granted when the API is enabled)
# doesn't include that permission.
resource "google_project_service_identity" "eventarc" {
  provider = google-beta
  project  = var.project_id
  service  = "eventarc.googleapis.com"
}

resource "google_storage_bucket_iam_member" "eventarc_agent_reads_intake" {
  bucket = var.intake_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_project_service_identity.eventarc.email}"
}

resource "google_eventarc_trigger" "ingest_on_object_finalized" {
  project  = var.project_id
  name     = "ingest-object-finalized"
  location = var.region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  matching_criteria {
    attribute = "bucket"
    value     = var.intake_bucket
  }

  destination {
    cloud_run_service {
      service = var.ingest_service_name
      region  = var.region
    }
  }

  service_account = var.ingest_service_account_email

  depends_on = [
    google_project_iam_member.gcs_agent_publishes_for_eventarc,
    google_storage_bucket_iam_member.eventarc_agent_reads_intake,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "ingest_invoker" {
  project  = var.project_id
  location = var.region
  name     = var.ingest_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.ingest_service_account_email}"
}
