import boto3
import collections
import json
import logging
import os
from datetime import datetime

import ldap
import ldap.asyncsearch


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
    log_file_name = 'ldap_maintainer.log'

logging.basicConfig(
    filename=log_file_name,
    format='%(asctime)s.%(msecs)03dZ [%(name)s][%(levelname)-5s]: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    level=LOG_LEVELS[os.environ.get('LOG_LEVEL', '').lower()])
log = logging.getLogger(__name__)


LDAPS_URL = os.environ['LDAPS_URL']
DOMAIN_BASE = os.environ['DOMAIN_BASE']
SSM_KEY = os.environ['SSM_KEY']
SVC_USER_DN = os.environ['SVC_USER_DN']

ssm = boto3.client('ssm')
SVC_USER_PWD = ssm.get_parameter(
    Name=SSM_KEY,
    WithDecryption=True
)['Parameter']['Value']


class LdapMaintainer:

    def __init__(self):
        """Initialize"""
        self.connection = self.connect()

    def filetime_to_dt(self, ft):
        """
        Convert windowsfiletime to python datetime.
        ref: https://gist.github.com/Mostafa-Hamdy-Elgiar/9714475f1b3bc224ea063af81566d873  # noqa: E501
        """
        # January 1, 1970 as MS file time
        epoch_as_filetime = 116444736000000000
        hundreds_of_nanoseconds = 10000000
        return datetime.utcfromtimestamp(
            (int(ft) - epoch_as_filetime) / hundreds_of_nanoseconds)

    def connect(self):
        """Establish a connection to the LDAP server."""
        log.debug("Attempting to connect to the LDAP server..")
        try:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
            con = ldap.initialize(LDAPS_URL)
            con.set_option(ldap.OPT_REFERRALS, 0)
            con.bind_s(SVC_USER_DN, SVC_USER_PWD)
            log.debug("Successfully connected to LDAP server.")
            return con
        except ldap.LDAPError:
            log.error("Failed to connect to the LDAP server.")

    def search(self, filter_string=None):
        """Search LDAP using the provided filter string."""
        log.debug("starting search with {}".format(filter_string))
        ldap_async = ldap.asyncsearch.List(self.connection)
        search_root = DOMAIN_BASE
        ldap_async.startSearch(
            search_root,
            ldap.SCOPE_SUBTREE,
            filter_string
        )

        try:
            partial = ldap_async.processResults()
        except ldap_async.SIZELIMIT_EXCEEDED:
            log.error("Warning: Server-side size limit exceeded")
        else:
            if partial:
                log.error("Warning: Only partial results received.")

        self.connection.unbind()
        return ldap_async.allResults

    def get_all_users(self):
        """Search LDAP and return all user objects."""
        return self.search("(&(objectCategory=person)(objectClass=user))")

    def get_users(self):
        """
        Returns a list of active users.
        User accounts in the target OU that have been previously disabled
        or configured with passwords that don't expire are ignored.
        """

        non_svc_users = []

        # code reference:
        # https://jackstromberg.com/2013/01/useraccountcontrol-attributeflag-values/
        disabled_codes = [
            "514",     # Disabled Account
            "65536",   # DONT_EXPIRE_PASSWORD
            "66048",   # Enabled, Password Doesn’t Expire
            "66050",   # Disabled, Password Doesn’t Expire
            "66080",   # Disabled, Password Doesn’t Expire & Not Required
            "262658",  # Disabled, Smartcard Required
            "262690"   # Disabled, Smartcard Required, Password Not Required
        ]
        # list of three letter prefixes to filter out of results
        filter_prefixes = json.loads(os.environ['FILTER_PREFIXES'])
        # list of accounts not to touch
        hands_off = json.loads(os.environ['HANDS_OFF_ACCOUNTS'])
        for user in self.get_all_users():
            try:
                uac = user[1][1]['userAccountControl'][0].decode("utf-8")
                ucn = user[1][1]['cn'][0].decode("utf-8")
                if (
                    uac not in disabled_codes and
                    ucn[:3] not in filter_prefixes and
                    ucn not in hands_off
                ):
                    # only add the user dict object back to the resulting list
                    non_svc_users.append(user[1][1])
            except TypeError:
                continue

        return non_svc_users

    def get_stale_users(self):
        """
        Returns object of users that have not logged on
        in 120, 90, and 60 day increments

        example:
        {
            "120": [userobj0, userobj1, etc..]
            "90": [userobj0, userobj1, etc..]
            "60": [userobj0, userobj1, etc..]
            "never": [userobj0, userobj1, etc..]
        }
        """
        stale_users = {
            "120": [],
            "90": [],
            "60": [],
            "never": []
        }
        today = datetime.now()
        for user in self.get_users():
            try:
                ft = user['pwdLastSet'][0].decode("utf-8")
                pwd_last_set = self.filetime_to_dt(ft)
                days = (today - pwd_last_set).days
                user = {
                    "name": user['cn'][0].decode("utf-8"),
                    "email": user['mail'][0].decode("utf-8"),
                    "dn": user['dn'][0].decode("utf-8"),
                    "days_since_last_pwd_change": days
                }
                if days >= 120:
                    stale_users["120"].append(user)
                elif days >= 90:
                    stale_users["90"].append(user)
                elif days >= 60:
                    stale_users["60"].append(user)
            except KeyError:
                stale_users["never"].append(user)
                continue
        return stale_users

    def get_ldif(self):
        """Creates a ldif document with the query results"""
        # could be an alternative way of user disablement


def create_table(content):
    """create a table"""
    # This can be fleshed out to make the retrieved information
    # more user friendly
    return json.dumps(content)


def generate_artifacts(content):
    """Returns the list of objects to upload to s3"""
    artifacts = {}
    artifacts['user_expiration_table'] = create_table(content)
    # artifacts.append(LdapMaintainer().get_ldif())
    return artifacts


def put_object(dest_bucket_name, dest_object_name, src_data):
    """
    Add an object to an Amazon S3 bucket
    """

    # Construct Body= parameter
    if isinstance(src_data, bytes):
        object_data = src_data
    else:
        log.error(f"Type of {str(type(src_data))}"
                  f" for the argument \'src_data\' is not supported.")
        return False

    # Put the object
    s3 = boto3.client('s3')
    log.debug(f"destination object name: {dest_object_name}")
    log.debug(f"destination bucket name: {dest_bucket_name}")
    try:
        s3.put_object(
            Bucket=dest_bucket_name,
            ACL="private",
            Key=dest_object_name,
            Body=object_data
            )
    except s3.exceptions.ClientError as e:
        # AllAccessDisabled error == bucket not found
        # NoSuchKey or InvalidRequest
        # error == (dest bucket/obj == src bucket/obj)
        log.error(e)
        return False
    finally:
        if isinstance(src_data, str):
            object_data.close()
    return True


def create_presigned_url(bucket_name, object_name, expiration=3600):
    s3 = boto3.client('s3')
    try:
        response = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_name
                },
            ExpiresIn=expiration
        )
    except s3.exceptions.ClientError as e:
        log.error(e)
        return None
    # The response contains the presigned URL
    return response


def upload_artifacts(content):
    presigned_urls = {}
    artifacts = generate_artifacts(content)
    bucket_name = os.environ['ARTIFACT_BUCKET']
    timestamp = datetime.now().strftime("%Y-%m-%d-T%H%M%S.%f")
    for key in artifacts:
        object_name = f"{key}-{timestamp}.json"
        log.debug(f'Uploading object: {object_name} to {bucket_name}')
        if put_object(
                bucket_name,
                object_name,
                artifacts[key].encode("utf-8")):
            presigned_urls[key] = create_presigned_url(
                bucket_name, object_name)
    return presigned_urls


def get_user_counts(users):
    response = {}
    for key in users:
        response[key] = len(users[key])
    return response


def handler(event, context):
    """
    expected event:
    {
        "action": query | disable
    }
    """
    log.debug(f'Received event: {event}')
    if event.get('Input'):
        event = event['Input']
    if event.get("action"):
        if event['action'] == "query":
            # users = LdapMaintainer().get_stale_users()
            users = {
                "120": ["user1", "user2", "user3"],
                "90": ["user1", "user2", "user3"],
                "60": ["user1", "user2", "user3"],
                "never": ["user1", "user2", "user3"],
            }
            log.debug(f"Ldap query results: {users}")
            return {
                "query_results": {
                    "totals": get_user_counts(users)
                },
                "artifact_urls": upload_artifacts(users),
                }
        elif event['action'] == "disable":
            # what does this look like?
            return {
                "user_details": []
            }
