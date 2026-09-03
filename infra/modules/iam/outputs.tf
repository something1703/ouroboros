output "service_account_emails" {
  value = { for k, sa in google_service_account.sa : k => sa.email }
}

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "ci_service_account_email" {
  value = google_service_account.sa["sa-ci-deploy"].email
}
