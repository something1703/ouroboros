variable "project_id" {
  description = "GCP project ID. One project, two envs by suffix (dev/demo)."
  type        = string
}

variable "region" {
  description = "Region for all regional resources (Cloud SQL, Cloud Run, Eventarc, VPC connector). Agent Engine and Gemini use 'global' separately."
  type        = string
  default     = "us-central1"
}

variable "env" {
  description = "Environment suffix: dev or demo."
  type        = string
  validation {
    condition     = contains(["dev", "demo"], var.env)
    error_message = "env must be 'dev' or 'demo'."
  }
}

variable "iap_users" {
  description = "Map of test-user email -> app role (legal|editorial|producer), for IAP in Phase 8."
  type        = map(string)
  default     = {}
}
