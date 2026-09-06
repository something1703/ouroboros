provider "google" {
  project = var.project_id
  region  = var.region
  # Found live (Phase 8.4, docs/DECISIONS.md): local `gcloud auth application-default
  # login` credentials attribute some API calls (discoveryengine.googleapis.com, the
  # first resource type this project has needed that apparently requires it) to the
  # gcloud CLI's own shared OAuth client project, not var.project_id, even with the
  # ADC file's own quota_project_id correctly set -- these two settings force every
  # request to bill/quota against var.project_id explicitly instead.
  user_project_override = true
  billing_project       = var.project_id
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}
