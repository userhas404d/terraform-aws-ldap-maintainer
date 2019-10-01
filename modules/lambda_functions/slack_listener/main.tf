data "aws_iam_policy_document" "lambda" {
  # need to make this less permissive
  statement {
    actions = [
      "states:*"
    ]
    resources = var.step_function_arns
  }
}

resource "aws_lambda_permission" "lambda_permission" {
  statement_id  = "AllowSlackNotifierInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = var.slack_listener_api_endpoint_arn
}

module "lambda" {
  source = "github.com/claranet/terraform-aws-lambda"

  function_name = "${var.project_name}-slack-listener"
  description   = "Listens for slack events."
  handler       = "lambda.handler"
  runtime       = "python3.7"
  timeout       = 30

  source_path = "${path.module}/lambda.py"

  environment = {
    variables = {
      SLACK_API_TOKEN      = var.slack_api_token
      SLACK_SIGNING_SECRET = var.slack_signing_secret
      LOG_LEVEL            = var.log_level
    }
  }

  policy = {
    json = data.aws_iam_policy_document.lambda.json
  }

}