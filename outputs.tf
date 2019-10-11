output "slack_listener_endpoint" {
  description = "Endpoint to add to slack"
  value       = "${module.api_gateway.invoke_url}/event-listener"
}