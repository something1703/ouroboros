variable "project_id" {
  type = string
}

variable "apis" {
  description = "Service names to enable, e.g. run.googleapis.com."
  type        = list(string)
}
