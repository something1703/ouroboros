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
