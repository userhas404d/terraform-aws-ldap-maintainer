variable "certificate_arn" {
  type        = string
  description = "ARN of the certificate to back the LDAPS endpoint"
}

variable "target_zone_name" {
  type        = string
  description = "Name of the zone in which to create the simplead DNS record"
}

variable "project_name" {
  type        = string
  default     = "ldapmaint-test"
  description = "Name of the project"
}

variable "directory_name" {
  type        = string
  description = "DNS name of the SimpleAD directory"
}

variable "slack_api_token" {
  description = "API token used by the slack client"
  type        = string
}

variable "slack_channel_id" {
  description = "Channel that the slack notifier will post to"
  type        = string
}

variable "slack_signing_secret" {
  default     = ""
  description = "The slack application's signing secret"
  type        = string
}