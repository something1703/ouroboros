output "instance_connection_name" {
  value = google_sql_database_instance.ouroboros.connection_name
}

output "private_ip_address" {
  value = google_sql_database_instance.ouroboros.private_ip_address
}

output "database_name" {
  value = google_sql_database.ouroboros.name
}

output "app_user" {
  value = google_sql_user.app.name
}
