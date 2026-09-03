output "intake_bucket" {
  value = google_storage_bucket.intake.name
}

output "artifacts_bucket" {
  value = google_storage_bucket.artifacts.name
}

output "fixtures_bucket" {
  value = google_storage_bucket.fixtures.name
}
