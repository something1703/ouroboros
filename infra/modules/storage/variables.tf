variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "env" {
  type = string
}

variable "cors_origins" {
  type        = list(string)
  description = "Browser origins allowed to fetch/upload bucket objects directly (the deployed web app, plus local dev)."
  default     = ["http://localhost:5173"]
}
