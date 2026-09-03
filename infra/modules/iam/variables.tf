variable "project_id" {
  type = string
}

variable "github_repo" {
  description = "owner/repo allowed to assume sa-ci via Workload Identity Federation."
  type        = string
  default     = "something1703/ouroboros"
}
