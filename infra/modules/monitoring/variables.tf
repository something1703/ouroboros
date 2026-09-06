variable "project_id" {
  type = string
}

variable "notification_email" {
  type        = string
  description = "Where Cloud Monitoring alert incidents are emailed (PHASE_09.md §9.4)."
}
