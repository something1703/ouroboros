output "db_password_secret_id" {
  value = google_secret_manager_secret.db_password.secret_id
}

output "db_password" {
  value     = random_password.db_password.result
  sensitive = true
}

output "parallel_api_key_secret_id" {
  value = google_secret_manager_secret.parallel_api_key.secret_id
}
