module "api_gateway" {
  source = "./modules/api_gateway"

  project_name                        = var.project_name
  lambda_function_arns                = ["${module.slack_event_listener.function_arn}"]
  slack_event_listener_sqs_arn        = module.slack_event_listener.sqs_queue_arn
  slack_event_listener_sqs_queue_name = module.slack_event_listener.sqs_queue_name
  slack_event_listener_lambda_arn     = module.slack_event_listener.function_invoke_arn
  slack_event_listener_lambda_name    = module.slack_event_listener.function_name
}

module "slack_event_listener" {
  source = "./modules/lambda_functions/slack_listener"

  project_name         = var.project_name
  slack_api_token      = var.slack_api_token
  slack_signing_secret = var.slack_signing_secret
  step_function_arns   = list(aws_sfn_state_machine.ldap_maintenance.id)
  api_gw_role_arn      = module.api_gateway.api_gw_role_arn

  slack_listener_api_endpoint_arn = module.api_gateway.slack_listener_api_endpoint_arn

  log_level = var.log_level
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

  log_level = var.log_level
}

module "slack_notifier" {
  source = "./modules/lambda_functions/slack_notifier"

  project_name     = var.project_name
  slack_channel_id = var.slack_channel_id
  slack_api_token  = var.slack_api_token
  sfn_activity_arn = aws_sfn_activity.account_deactivation_approval.id
  invoke_base_url  = module.api_gateway.invoke_url

  log_level = var.log_level
}

module "dynamodb_cleanup" {
  source = "./modules/lambda_functions/dynamodb_cleanup"

  project_name        = var.project_name
  dynamodb_table_name = var.dynamodb_table_name

  log_level = var.log_level
}

# step function 
data "aws_iam_policy_document" "sfn" {
  statement {
    actions = [
      "lambda:InvokeFunction"
    ]
    resources = [
      module.ldap_query_lambda.function_arn,
      module.slack_notifier.function_arn,
      module.dynamodb_cleanup.function_arn
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
    "Next": "wait_for_manual_approval"
    },

    "wait_for_manual_approval": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
      "Parameters": {
            "FunctionName": "${module.slack_notifier.function_name}",
            "Payload":{  
               "event.$": "$",
               "token.$": "$$.Task.Token"
            }
      },
      "Next": "check_manual_approval"
    },

    "check_manual_approval": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.button_pressed",
          "StringEquals": "Approve",
          "Next": "notify_slack_of_approval"
        }
      ],
      "Default": "notify_slack_of_disapproval"
    },

    "notify_slack_of_disapproval": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
            "FunctionName": "${module.slack_notifier.function_name}",
            "Payload":{  
               "event.$": "$",
               "message_to_slack": "The LDAP operation has been disapproved"
            }
      },
      "Next": "disapproved"
    },

    "disapproved": {
      "Type": "Fail",
      "Cause": "No Matches!"
    },

    "notify_slack_of_approval": {
    "Type": "Task",
    "Resource": "arn:aws:states:::lambda:invoke",
    "Parameters": {
      "FunctionName": "${module.slack_notifier.function_name}",
      "Payload": {
        "event.$": "$",
        "message_to_slack": "The LDAP operation has been approved. I'll notify you when the operation is complete."
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
        "action": "disable",
        "event.$": "$"
      }
    },
    "Next": "dynamodb_cleanup"
    },

    "dynamodb_cleanup": {
    "Type": "Task",
    "Resource": "arn:aws:states:::lambda:invoke",
    "Parameters": {
      "FunctionName": "${module.dynamodb_cleanup.function_arn}",
      "Payload": {
        "event.$": "$"
      }
    },
    "Next": "send_status_to_slack"
    },

    "send_status_to_slack": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
            "FunctionName": "${module.slack_notifier.function_name}",
            "Payload":{
               "event.$": "$",
               "message_to_slack": "LDAP operations are complete"
            }
      },
     "End": true
    }

  }
}
EOF
}