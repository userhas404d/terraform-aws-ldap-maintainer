
"""
Slack chat-bot Lambda handler.
"""
import boto3
import collections
import json
import os
import hmac
import hashlib
import logging
from urllib.parse import unquote

DEFAULT_LOG_LEVEL = logging.DEBUG
LOG_LEVELS = collections.defaultdict(
    lambda: DEFAULT_LOG_LEVEL,
    {
        'critical': logging.CRITICAL,
        'error': logging.ERROR,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }
)

# Lambda initializes a root logger that needs to be removed in order to set a
# different logging config
root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)

log_file_name = ""
if not os.environ.get("AWS_EXECUTION_ENV"):
    log_file_name = 'ldap_maintainer_slack.log'

logging.basicConfig(
    filename=log_file_name,
    format='%(asctime)s.%(msecs)03dZ [%(name)s][%(levelname)-5s]: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    level=LOG_LEVELS[os.environ.get('LOG_LEVEL', '').lower()])
log = logging.getLogger(__name__)

# stolen largely from:
# https://chatbotslife.com/write-a-serverless-slack-chat-bot-using-aws-e2d2432c380e

# Grab the Bot OAuth token from the environment.
BOT_TOKEN = os.environ["SLACK_API_TOKEN"]

# Define the URL of the targeted Slack API resource.
# We'll send our replies there.
SLACK_URL = "https://slack.com/api/chat.postMessage"


def get_http_response(httpStatusCode, body, headers={}):
    return {
        "isBase64Encoded": False,
        "statusCode": httpStatusCode,
        "headers": headers,
        "body": body
        }


def get_slack_payload(req):
    """
    Extract the body data of the slack request.
    """

    if req.get("body"):
        extracted_data = json.loads(unquote(req['body']).replace("payload=", ""))
        # log.info(f'Extracted data: {extracted_data}')
        return extracted_data


def notify_stepfunction(slack_payload):
    """Sends a task token to the step function service"""
    action_id = slack_payload['actions'][0]['action_id']
    task_token = unquote(slack_payload['actions'][0]['value'])
    sfn = boto3.client("stepfunctions")
    if action_id.lower() == "approve":
        sfn.send_task_success(
            taskToken=task_token,
            output="\"Approve link was clicked.\""
        )
    else:
        sfn.send_task_failure(
            taskToken=task_token,
            error='Denied',
            cause='Action denied'
        )


# borrowed largely from here:
# https://github.com/codelabsab/timereport-slack/blob/master/chalicelib/lib/slack.py
def verify_token(headers, body, signing_secret):
    """
    https://api.slack.com/docs/verifying-requests-from-slack
    1. Grab timestamp and slack signature from headers.
    2. Concat and create a signature with timestamp + body
    3. Hash the signature together with
        your signing_secret token from slack settings
    4. Compare digest to slack signature from header
    """
    request_timestamp = headers['X-Slack-Request-Timestamp'][0]
    slack_signature = headers['X-Slack-Signature'][0]

    request_basestring = f'v0:{request_timestamp}:{body}'
    my_sig = hmac.new(
        bytes(signing_secret, "utf-8"),
        bytes(request_basestring, "utf-8"),
        hashlib.sha256).hexdigest()
    my_sig = f'v0={my_sig}'

    if hmac.compare_digest(my_sig, slack_signature):
        return True
    else:
        return False


def handler(event, context):
    log.debug(f"received event: {event}")

    slack_headers = event['multiValueHeaders']
    SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']

    if verify_token(slack_headers, event['body'], SLACK_SIGNING_SECRET):
        notify_stepfunction(get_slack_payload(event))
        return get_http_response("200", "Success!")
    else:
        return get_http_response("403", "Message hashes do not match.")
