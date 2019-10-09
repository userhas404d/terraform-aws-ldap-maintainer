variable "project_name" {
  default     = "ldap-maintainer"
  description = "Name of the project"
  type        = string
}

variable "log_level" {
  default     = "Info"
  description = "Log level of the lambda output, one of: Debug, Info, Warning, Error, or Critical"
  type        = string
}

variable "tags" {
  default     = {}
  description = "Map of tags"
  type        = map(string)
}

variable "dynamodb_table_name" {
  description = "Name of the dynamodb to take actions against"
  type        = string
}