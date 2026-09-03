variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "intake_bucket" {
  type = string
}

variable "ingest_service_account_email" {
  type = string
}

variable "ingest_service_name" {
  type    = string
  default = "ingest"
}
