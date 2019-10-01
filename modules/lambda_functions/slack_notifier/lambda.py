import collections
import logging
import os
from datetime import datetime

import slack


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


class SlackMessageBuilder:
    """Constructs slack messages"""

    INVOKE_BASE_URL = os.environ['INVOKE_BASE_URL']

    HEADER_BLOCK = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "A scan of our LDAP directory has been completed."
            }
        }

    DIVIDER_BLOCK = {"type": "divider"}

    CONFIRMATION_BLOCK = {
        "title": {
            "type": "plain_text",
            "text": "Are you sure?"
        },
        "text": {
            "type": "mrkdwn",
            "text": "Are you sure you want to take this action?"
        },
        "confirm": {
            "type": "plain_text",
            "text": "Yes"
        },
        "deny": {
            "type": "plain_text",
            "text": "No"
        }
        }

    def __init__(
            self,
            channel,
            artifact_urls,
            user_counts,
            report_time,
            task_token):
        self.channel = channel
        self.username = "ldapmaintainerbot"
        self.icon_emoji = ":robot_face:"
        self.timestamp = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        self.artifact_urls = artifact_urls
        self.user_counts = user_counts
        self.report_time = report_time
        self.task_token = task_token

    def get_message_payload(self):
        return {
            "ts": self.timestamp,
            "channel": self.channel,
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "blocks": [
                self.HEADER_BLOCK,
                self.DIVIDER_BLOCK,
                self._get_artifact_urls_block(),
                self.DIVIDER_BLOCK,
                self._get_buttons_block(),
                self._get_context_block()
            ]
        }

    def _get_artifact_urls_block(self):
        text = (
            f"Total counts of users with passwords"
            f" that have not been changed in.."
            f"\n\t greater than 120 days: {self.user_counts['120']}"
            f"\n\t gerater than 90 days: {self.user_counts['90']}"
            f"\n\t greater than 60 days: {self.user_counts['60']}"
            f"\n\n full details available here: ")
        for url in self.artifact_urls:
            text += f"<{self.artifact_urls[url]}|{url}>\n"
        text += (
            f"\n *Note*: When this message is 30 days old the "
            f"attached document urls will no longer be functional\n\n"
            f"\n Select Approve or Deny to disable the accounts that"
            f" have not updated their passwords in greater than 120 days"
            )
        return self._get_text_block(text)

    def _get_context_block(self):
        return {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Report Generated: {self.report_time}"
                }
            ]
        }

    def _get_buttons_block(self):
        return {
            "type": "actions",
            "elements": self._get_buttons()
        }

    def _get_buttons(self):
        actions = ["deny", "approve"]
        buttons = []
        for action in actions:
            if action == "approve":
                style = "primary"
            else:
                style = "danger"
            buttons.append(
                self._get_button(
                    action.capitalize(),
                    self.task_token,
                    style
                )
            )
        return buttons

    def _get_button(self, text, value, style):
        return {
            "type": "button",
            "text": {"type": "plain_text", "text": text},
            "value": value,
            "action_id": text,
            "confirm": self.CONFIRMATION_BLOCK,
            "style": style
            }

    @staticmethod
    def _get_text_block(text):
        return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def build_slack_user_message(payload, task_token):
    TARGET_CHANNEL = os.environ['SLACK_CHANNEL_ID']
    message_body = SlackMessageBuilder(
        channel=TARGET_CHANNEL,
        artifact_urls=payload['artifact_urls'],
        user_counts=payload['query_results']['totals'],
        report_time=datetime.now().strftime("%m/%d, %Y"),
        task_token=task_token
    )
    message = message_body.get_message_payload()
    return message


def build_slack_response_message():
    """"""


def send_message_to_slack(message):
    """Sends the user status report to slack."""
    SLACK_API_TOKEN = os.environ['SLACK_API_TOKEN']
    client = slack.WebClient(token=SLACK_API_TOKEN)
    response = client.chat_postMessage(**message)
    assert response["ok"]


def handler(event, context):
    # try catch to get task token,
    # if tasktoken then pass to slack..
    log.debug(f"Received event: {event}")
    task_token = event['token']

    payload = event['event']['Payload']
    slack_message = build_slack_user_message(payload, task_token)
    send_message_to_slack(slack_message)
    return payload
