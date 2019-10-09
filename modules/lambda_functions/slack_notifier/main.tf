
resource "random_string" "this" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_lambda_layer_version" "lambda_layer" {
  filename         = "${path.module}/lambda_layer_payload.zip"
  layer_name       = "python-ldap-${random_string.this.result}"
  description      = "Contains python-ldap and its dependencies"
  source_code_hash = "${filebase64sha256("${path.module}/lambda_layer_payload.zip")}"

  compatible_runtimes = ["python3.7"]
}

module "lambda" {
  source = "github.com/claranet/terraform-aws-lambda"

  function_name = "${var.project_name}-slack-notifier-${random_string.this.result}"
  description   = "Sends alerts to slack and performs ldap maintenance tasks"
  handler       = "lambda.handler"
  runtime       = "python3.7"
  timeout       = 30

  source_path = "${path.module}/lambda.py"

  environment = {
    variables = {
      SLACK_API_TOKEN  = var.slack_api_token
      SLACK_CHANNEL_ID = var.slack_channel_id
      SFN_ACTIVITY_ARN = var.sfn_activity_arn
      INVOKE_BASE_URL  = var.invoke_base_url
      TIMEZONE         = var.timezone
      LOG_LEVEL        = var.log_level
    }
  }

  layers = [aws_lambda_layer_version.lambda_layer.arn]
}