module "api_gateway" {
  source = "./modules/api_gateway"

  lambda_function_arns             = ["${module.slack_event_listener.function_arn}"]
  slack_event_listener_lambda_arn  = module.slack_event_listener.function_invoke_arn
  slack_event_listener_lambda_name = module.slack_event_listener.function_name
}

module "slack_event_listener" {
  source = "./modules/lambda_functions/slack_listener"

  slack_api_token      = var.slack_api_token
  slack_signing_secret = var.slack_signing_secret
  step_function_arns   = list(aws_sfn_state_machine.ldap_maintenance.id)

  slack_listener_api_endpoint_arn = module.api_gateway.slack_listener_api_endpoint_arn

  log_level = "Debug"
}

module "ldap_query_lambda" {
  source = "./modules/lambda_functions/ldap_query"

  project_name         = var.project_name
  ldaps_url            = var.ldaps_url
  domain_base_dn       = var.domain_base_dn
  filter_prefixes      = var.filter_prefixes
  svc_user_dn          = var.svc_user_dn
  svc_user_pwd_ssm_key = var.svc_user_pwd_ssm_key
  vpc_id               = var.vpc_id

  log_level = "Debug"
}

module "manual_step_activity_worker" {
  source = "./modules/lambda_functions/slack_notifier"

  project_name     = var.project_name
  slack_channel_id = var.slack_channel_id
  slack_api_token  = var.slack_api_token
  sfn_activity_arn = aws_sfn_activity.account_deactivation_approval.id
  invoke_base_url  = module.api_gateway.invoke_url

  log_level = "Debug"
}

# step function 
data "aws_iam_policy_document" "sfn" {
  statement {
    actions = [
      "lambda:InvokeFunction"
    ]
    resources = [
      module.ldap_query_lambda.function_arn,
      module.manual_step_activity_worker.function_arn
    ]
  }
}

resource "aws_iam_policy" "sfn" {
  name        = "${var.project_name}-sfn"
  description = "Policy used by the Ldap Maintenance Step Function"
  policy      = "${data.aws_iam_policy_document.sfn.json}"
}

data "template_file" "sfn_trust" {
  template = "${file("${path.module}/policies/trust.json")}"
  vars = {
    service = "states.amazonaws.com"
  }
}

resource "aws_iam_role" "sfn" {
  name = "${var.project_name}-sfn"

  assume_role_policy = data.template_file.sfn_trust.rendered
}

resource "aws_iam_policy_attachment" "sfn" {
  name       = "ldap-maintainer-sfn"
  roles      = ["${aws_iam_role.sfn.name}"]
  policy_arn = "${aws_iam_policy.sfn.arn}"
}

resource "aws_sfn_activity" "account_deactivation_approval" {
  name = "account_deactivation_approval"
}

resource "aws_sfn_state_machine" "ldap_maintenance" {
  name     = var.project_name
  role_arn = "${aws_iam_role.sfn.arn}"

  definition = <<EOF
{
  "Comment": "Ldap account deactivation manager",
  "StartAt": "run_ldap_query",
  "States": {
    "run_ldap_query": {
    "Type": "Task",
    "Resource": "arn:aws:states:::lambda:invoke",
    "Parameters": {
      "FunctionName": "${module.ldap_query_lambda.function_arn}",
      "Payload": {
        "Input": {"action": "query"}
      }
    },
    "Next": "manual_approval"
    },
    "manual_approval": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
      "Parameters": {
            "FunctionName":"${module.manual_step_activity_worker.function_name}",
            "Payload":{  
               "event.$":"$",
               "token.$":"$$.Task.Token"
            }
      },
      "Next": "run_ldap_query_again"
    },
    "run_ldap_query_again": {
    "Type": "Task",
    "Resource": "arn:aws:states:::lambda:invoke",
    "Parameters": {
      "FunctionName": "${module.ldap_query_lambda.function_arn}",
      "Payload": {
        "Input": {"Action": "RunQuery"}
      }
    },
    "End": true
    }
  }
}
EOF
}