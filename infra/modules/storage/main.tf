# Bucket names are prefixed with the project ID for global uniqueness (GCS bucket
# names are global across all of Google Cloud, not just this project) — see
# docs/DECISIONS.md for the naming deviation from the plan's `ouroboros-intake-{env}`.

resource "google_storage_bucket" "intake" {
  project                     = var.project_id
  name                        = "${var.project_id}-intake-${var.env}"
  location                    = var.region
  uniform_bucket_level_access = true
  versioning {
    enabled = true
  }
}

# Vertex AI's own Gemini service agent (not sa-ingest, not whoever calls the API) needs
# read access to a gs:// object before it will fetch it for types.Part.from_uri — found
# live: extract_script_claims failed with a 403 from
# service-<project-number>@gcp-sa-aiplatform.iam.gserviceaccount.com until this was
# granted. See docs/DECISIONS.md.
resource "google_project_service_identity" "vertex_ai" {
  provider = google-beta
  project  = var.project_id
  service  = "aiplatform.googleapis.com"
}

resource "google_storage_bucket_iam_member" "vertex_ai_reads_intake" {
  bucket = google_storage_bucket.intake.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_project_service_identity.vertex_ai.email}"
}

resource "google_storage_bucket" "artifacts" {
  project                     = var.project_id
  name                        = "${var.project_id}-artifacts-${var.env}"
  location                    = var.region
  uniform_bucket_level_access = true
}

# Shared across envs — large sample fixtures (scripts, cuts) are not env-specific.
resource "google_storage_bucket" "fixtures" {
  project                     = var.project_id
  name                        = "${var.project_id}-fixtures"
  location                    = var.region
  uniform_bucket_level_access = true
}
