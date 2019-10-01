
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}


# create the role that API Gateway can use to call Step Functions.
data "template_file" "api_gw_trust" {
  template = "${file("${path.module}/../../policies/trust.json")}"
  vars = {
    service = "apigateway.amazonaws.com"
  }
}

data "aws_iam_policy_document" "api_gw" {
  statement {
    actions = [
      "lambda:InvokeFunction"
    ]
    resources = var.lambda_function_arns
  }
}

resource "aws_iam_policy" "api_gw" {
  name        = "${var.project_name}-api-gw"
  description = "Policy used by the Ldap Maintenance API Gateway"
  policy      = "${data.aws_iam_policy_document.api_gw.json}"
}

resource "aws_iam_role" "api_gw" {
  name = "${var.project_name}-api-gw"

  assume_role_policy = data.template_file.api_gw_trust.rendered

  tags = var.tags
}

resource "aws_iam_policy_attachment" "api_gw" {
  name       = "ldap-maintainer-api-gw"
  roles      = ["${aws_iam_role.api_gw.name}"]
  policy_arn = "${aws_iam_policy.api_gw.arn}"
}

# Create the api
# largely stolen from here:
# https://aws.amazon.com/blogs/compute/implementing-serverless-manual-approval-steps-in-aws-step-functions-and-amazon-api-gateway/
resource "aws_api_gateway_rest_api" "api" {
  name        = "${var.project_name}-api"
  description = "API for managing LDAP maintenance tasks"
}

# resource "aws_api_gateway_resource" "approve" {
#   rest_api_id = "${aws_api_gateway_rest_api.api.id}"
#   parent_id   = "${aws_api_gateway_rest_api.api.root_resource_id}"
#   path_part   = "approve"
# }

# resource "aws_api_gateway_resource" "deny" {
#   rest_api_id = "${aws_api_gateway_rest_api.api.id}"
#   parent_id   = "${aws_api_gateway_rest_api.api.root_resource_id}"
#   path_part   = "deny"
# }

resource "aws_api_gateway_resource" "event_listener" {
  rest_api_id = "${aws_api_gateway_rest_api.api.id}"
  parent_id   = "${aws_api_gateway_rest_api.api.root_resource_id}"
  path_part   = "event-listener"
}

# resource "aws_api_gateway_method" "approve_get" {
#   rest_api_id   = "${aws_api_gateway_rest_api.api.id}"
#   resource_id   = "${aws_api_gateway_resource.approve.id}"
#   http_method   = "GET"
#   authorization = "NONE"
#   request_parameters = {
#     "method.request.querystring.taskToken" = true
#   }
# }

# resource "aws_api_gateway_method" "deny_get" {
#   rest_api_id   = "${aws_api_gateway_rest_api.api.id}"
#   resource_id   = "${aws_api_gateway_resource.deny.id}"
#   http_method   = "GET"
#   authorization = "NONE"
#   request_parameters = {
#     "method.request.querystring.taskToken" = true
#   }
# }

resource "aws_api_gateway_method" "event_listener_post" {
  rest_api_id   = "${aws_api_gateway_rest_api.api.id}"
  resource_id   = "${aws_api_gateway_resource.event_listener.id}"
  http_method   = "POST"
  authorization = "NONE"
}

# resource "aws_api_gateway_integration" "approve" {
#   rest_api_id             = "${aws_api_gateway_rest_api.api.id}"
#   resource_id             = "${aws_api_gateway_resource.approve.id}"
#   http_method             = "${aws_api_gateway_method.approve_get.http_method}"
#   credentials             = "${aws_iam_role.api_gw.arn}"
#   integration_http_method = "POST"
#   type                    = "AWS"
#   uri                     = "arn:aws:apigateway:${data.aws_region.current.name}:states:action/SendTaskSuccess"
#   passthrough_behavior    = "WHEN_NO_TEMPLATES"
#   request_templates = {
#     "application/json" = <<EOF
#     {
#       "output": "\"Approve link was clicked.\"",
#       "taskToken": "$input.params('taskToken')"
#     }
#     EOF

#   }
# }

# resource "aws_api_gateway_integration" "deny" {
#   rest_api_id             = "${aws_api_gateway_rest_api.api.id}"
#   resource_id             = "${aws_api_gateway_resource.deny.id}"
#   http_method             = "${aws_api_gateway_method.deny_get.http_method}"
#   credentials             = "${aws_iam_role.api_gw.arn}"
#   integration_http_method = "POST"
#   type                    = "AWS"
#   uri                     = "arn:aws:apigateway:${data.aws_region.current.name}:states:action/SendTaskFailure"
#   passthrough_behavior    = "WHEN_NO_TEMPLATES"
#   request_templates = {
#     "application/json" = <<EOF
#     {
#       "cause": "Deny link was clicked.",
#       "error": "Deny",
#       "taskToken": "$input.params('taskToken')"
#     }
#     EOF
#   }
# }

resource "aws_api_gateway_integration" "event_listener" {
  rest_api_id             = "${aws_api_gateway_rest_api.api.id}"
  resource_id             = "${aws_api_gateway_resource.event_listener.id}"
  http_method             = "${aws_api_gateway_method.event_listener_post.http_method}"
  credentials             = "${aws_iam_role.api_gw.arn}"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${var.slack_event_listener_lambda_arn}"
}

resource "aws_api_gateway_method_response" "event_listener_response_200" {
  rest_api_id = "${aws_api_gateway_rest_api.api.id}"
  resource_id = "${aws_api_gateway_resource.event_listener.id}"
  http_method = "${aws_api_gateway_method.event_listener_post.http_method}"
  status_code = "200"
}

resource "aws_api_gateway_integration_response" "event_listener_response_200" {
  depends_on = [
    "aws_api_gateway_integration.event_listener"
  ]
  rest_api_id = "${aws_api_gateway_rest_api.api.id}"
  resource_id = "${aws_api_gateway_resource.event_listener.id}"
  http_method = "${aws_api_gateway_method.event_listener_post.http_method}"
  status_code = "${aws_api_gateway_method_response.event_listener_response_200.status_code}"
}

# deploy the api
resource "aws_api_gateway_deployment" "respond" {
  depends_on = [
    "aws_api_gateway_integration.event_listener"
  ]
  rest_api_id = "${aws_api_gateway_rest_api.api.id}"
  stage_name  = "respond"
}