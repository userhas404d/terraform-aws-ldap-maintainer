
"""
Slack chat-bot Lambda handler.
"""
import boto3
import collections
import os
import logging

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


dyanmodb = boto3.client('dynamodb')
dynamodb_resource = boto3.resource('dynamodb')
table = dynamodb_resource.Table(os.environ['DYNAMODB_TABLE'])


def scan_table(scan_attributes):
    """
    Scan the target table by attribute list.
    """
    return table.scan(
            AttributesToGet=scan_attributes,
        )


def modify_scan_results(email_address, scan_results):
    for item in scan_results['Items']:
        try:
            for distro in item['email_distros']:
                email_distro = item['email_distros'][distro]
                if email_address in email_distro:
                    email_distro.remove(email_address)
                    item['has_updates'] = True
                    log.info(f"removed {email_address} from {distro}")
        except KeyError:
            continue
    return scan_results


def apply_scan_results(updated_scan_results):
    for item in updated_scan_results['Items']:
        if item['has_updates']:
            table.update_item(
                Key={
                    "account_name": item["account_name"]
                },
                UpdateExpression="set email_distros = :distros",
                ExpressionAttributeValues={
                    ":distros": item['email_distros']
                },
                ReturnValues="UPDATED_NEW"
            )
            print(f"updated {item['account_name']}")


# this should probably be called recursively for all users in the input list
# otherwise this task will be very 'chatty'
# https://realpython.com/python-thinking-recursively/
def remove_user(email, scan_results):
    updated_scan_results = modify_scan_results(email, scan_results)
    apply_scan_results(updated_scan_results)


def remove_users_in_list(users):
    scan_attributes = ['account_name', 'email_distros']
    scan_results = scan_table(scan_attributes)
    for user in users:
        remove_user(user['email'], scan_results)


# def handler(event, context):
#     log.debug(f"Received event: {event}")
#     return event
