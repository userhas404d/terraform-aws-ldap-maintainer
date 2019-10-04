variable "tags" {
  default     = {}
  description = "Map of tags"
  type        = map(string)
}

variable "project_name" {
  default     = "ldap-maintainer"
  description = "Name of the project"
  type        = string
}

variable "slack_event_listener_lambda_arn" {
  default     = ""
  description = "Invocation ARN of the slack event listener"
  type        = string
}

variable "slack_event_listener_lambda_name" {
  default     = ""
  description = "Name of the slack event listener lambda"
  type        = string
}

variable "lambda_function_arns" {
  default     = []
  description = "List of lambda ARNS that the resulting api gateway can invoke"
  type        = list(string)
}

variable "slack_event_listener_sqs_arn" {
  type = string
}

variable "slack_event_listener_sqs_queue_name" {
  type = string
}