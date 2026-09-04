variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "sa_scheduler_email" {
  description = "Identity the push subscription's OIDC token authenticates as when calling dashboard-api."
  type        = string
}

variable "dashboard_api_service_name" {
  type    = string
  default = "dashboard-api"
}
