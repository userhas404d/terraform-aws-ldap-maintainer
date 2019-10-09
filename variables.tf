variable "project_name" {
  default     = "ldap-maintainer"
  description = "Name of the project"
  type        = string
}

variable "ldaps_url" {
  description = "LDAPS URL for the target domain"
  type        = string
}

variable "domain_base_dn" {
  description = "Distinguished name of the domain"
  type        = string
}

variable "svc_user_dn" {
  description = "Distinguished name of the user account used to manage simpleAD"
  type        = string
}

variable "svc_user_pwd_ssm_key" {
  description = "SSM parameter key that contains the service account password"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID of the VPC hosting your Simple AD instance"
  type        = string
}

variable "slack_api_token" {
  description = "API token used by the slack client"
  type        = string
}

variable "slack_channel_id" {
  description = "Channel that the slack notifier will post to"
  type        = string
}

variable "log_level" {
  default     = "Info"
  description = "Log level of the lambda output, one of: Debug, Info, Warning, Error, or Critical"
  type        = string
}

variable "slack_signing_secret" {
  default     = ""
  description = "The slack application's signing secret"
  type        = string
}

variable "filter_prefixes" {
  default     = []
  description = "List of three letter user name prefixes to filter out of the user search results"
  type        = list(string)
}

variable "dynamodb_table_name" {
  description = "Name of the dynamodb to take actions against"
  type        = string
}