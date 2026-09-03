variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "env" {
  type = string
}

variable "subnet_cidr" {
  type    = string
  default = "10.10.0.0/20"
}

variable "connector_cidr" {
  description = "Must be a /28 not overlapping the subnet, per Serverless VPC Access requirements."
  type        = string
  default     = "10.10.16.0/28"
}
