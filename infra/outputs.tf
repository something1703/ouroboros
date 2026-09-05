output "vpc_network" {
  value = module.network.network_name
}

output "vpc_connector_id" {
  value = module.network.vpc_connector_id
}

output "artifact_registry_url" {
  value = module.artifact_registry.repository_url
}

output "intake_bucket" {
  value = module.storage.intake_bucket
}

output "artifacts_bucket" {
  value = module.storage.artifacts_bucket
}

output "fixtures_bucket" {
  value = module.storage.fixtures_bucket
}

output "service_account_emails" {
  value = module.iam.service_account_emails
}

output "ci_workload_identity_provider" {
  value = module.iam.workload_identity_provider
}

output "ci_service_account_email" {
  value = module.iam.ci_service_account_email
}

output "cloud_sql_connection_name" {
  value = module.cloud_sql.instance_connection_name
}

output "cloud_sql_private_ip" {
  value = module.cloud_sql.private_ip_address
}
