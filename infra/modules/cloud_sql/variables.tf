variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "env" {
  type = string
}

variable "vpc_network_id" {
  type = string
}

variable "private_service_connection" {
  description = "The network.google_service_networking_connection resource — Cloud SQL private IP needs the peering range it creates."
  type        = string
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "deletion_protection" {
  type    = bool
  default = false # hackathon; flip to true once `demo` is frozen (Phase 9.7)
}

variable "enable_public_ip" {
  description = <<-EOT
    Off by default — the instance is private-IP-only. Flip to true only to run the
    Cloud SQL Auth Proxy from a machine outside the VPC (e.g. a developer laptop, per
    PHASE_02.md §2.2's "alembic upgrade head ... via Cloud SQL Auth Proxy" acceptance
    check) — the proxy's default mode needs a public IP to dial even though the
    connection itself stays TLS/IAM-authenticated end to end. Turn back off after.
    Cloud Run and other in-VPC services never need this — they reach the private IP
    directly via the Serverless VPC Access connector.
  EOT
  type        = bool
  default     = false
}
