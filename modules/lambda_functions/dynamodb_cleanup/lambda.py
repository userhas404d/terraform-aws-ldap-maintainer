
"""
Slack chat-bot Lambda handler.
"""
import boto3
import collections
import json
import logging
import os

s3 = boto3.client('s3')

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


def get_last_modified():
    return lambda obj: int(obj['LastModified'].strftime('%s'))


def get_latest_s3_object(
    bucket=os.environ['ARTIFACTS_BUCKET'],
    prefix='user_expiration_table'
):
    """
    Retrieve the newest object in the target s3 bucket
    """
    response = s3.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix)
    all = response['Contents']
    return max(all, key=lambda x: x['LastModified'])


def retrieve_s3_object_contents(
    s3_obj,
    bucket=os.environ['ARTIFACTS_BUCKET']
):
    return json.loads(s3.get_object(
        Bucket=bucket,
        Key=s3_obj['Key']
        )['Body'].read().decode('utf-8'))


def get_previous_scan_results():
    s3_obj = get_latest_s3_object()
    return retrieve_s3_object_contents(s3_obj)


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


def handler(event, context):
    log.debug(f"Received event: {event}")
    if event.get('Input'):
        event = event['Input']
    if event['action'] == "remove":
        users = get_previous_scan_results()['120']
        remove_users_in_list(users)
        log.info('Successfully removed the stale users from dynamodb')
