resource "google_artifact_registry_repository" "ouroboros" {
  project       = var.project_id
  location      = var.region
  repository_id = "ouroboros"
  format        = "DOCKER"
  description   = "Container images for Ouroboros Cloud Run services and Agent Engine deployments."
}
