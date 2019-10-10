import collections
import logging
import os
from datetime import datetime

import ldap
import ldap.asyncsearch
import ldap.modlist


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
SVC_USER_DN = os.environ['SVC_USER_DN']
SVC_USER_PWD = os.environ['SVC_USER_PWD']


class LdapMaintainer:

    def __init__(self):
        self.connection = self.connect()

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

    @staticmethod
    def byte_decode_search_results(search_results):
        """
        Byte decodes user search results from LDAP
        returns a list of user dictionaries

        output:
        [
            {
                "dn" = "cn=John Smith,CN=Users,DC=foo,DC=bar,DC=com",
                "user" = {
                    "givenName": ['John']
                    ...
                }
            },
            {
                "dn" = "cn=Jane Doe,CN=Users,DC=foo,DC=bar,DC=com",
                "user" = {
                    "givenName": ['Jane']
                    ...
                }
            }
        ]
        """
        users = []
        for user in search_results:
            user_obj = {}
            for attribute in user[1][1]:
                try:
                    attribute_list = user[1][1][attribute]
                    for i in range(len(attribute_list)):
                        try:
                            attribute_list[i] = (
                                attribute_list[i].decode('utf-8'))
                        except UnicodeDecodeError:
                            # ignore the user's GUID and SID
                            attribute_list[i] = "ignored"
                            continue
                except TypeError:
                    # some elements are already strings so
                    # just continue past them
                    continue
            user_obj['dn'] = user[1][0]
            user_obj['user'] = user[1][1]
            users.append(user_obj)
        return users

    def get_all_users(self):
        """Search LDAP and return all user objects."""
        return self.byte_decode_search_results(
            self.search("(&(objectCategory=person)(objectClass=user))"))

    def add_users(self, user_list):
        con = self.connect()
        for user_obj in user_list:
            try:
                con.add_s(
                    user_obj['dn'],
                    ldap.modlist.addModlist(user_obj['user']))
            except ldap.ALREADY_EXISTS:
                continue

    def disable_users(self, user_list):
        con = self.connect()
        date = datetime.now().strftime("%Y-%m-%d-T%H%M%S.%f")
        d = f"***Disabled {date} by ldapmaintbot***"
        for user_obj in user_list:
            disable_user = [(
                ldap.MOD_REPLACE,
                'userAccountControl',
                [b'66050'])]
            update_description = [(
                ldap.MOD_REPLACE,
                'description',
                [d.encode('utf-8')])]
            con.modify_s(user_obj['dn'], disable_user)
            con.modify_s(user_obj['dn'], update_description)


def byte_encode_user_map(input_map):
    """
    Performs byte encode operations on LDAP user objects
    """
    for element in input_map:
        element_list = input_map[element]
        for i in range(len(element_list)):
            element_list[i] = element_list[i].encode('utf-8')
    return input_map


def generate_test_user_objects(test_users):
    """
    Creates a list of dictionaries with a user's distingushed name (dn)
    and byte encoded user object provided a list of names in
    "Firstname Lastname" format

    input:

    [
        "John Smith",
        "Jane Doe"
    ]

    output:

    [
        {
            "dn" = "cn=John Smith,CN=Users,DC=foo,DC=bar,DC=com",
            "user" = {
                "givenName": [b'John']
                ...
            }
        },
        {
            "dn" = "cn=Jane Doe,CN=Users,DC=foo,DC=bar,DC=com",
            "user" = {
                "givenName": [b'Jane']
                ...
            }
        }
    ]
    """
    user_list = []
    for user in test_users:
        name = user.split()
        user_obj = {}
        user_obj['dn'] = f"cn={user},CN=Users,{DOMAIN_BASE}"
        user_obj['user'] = byte_encode_user_map({
                "cn": [user],
                "displayName": [f"Test account {user}"],
                "description": ["Test account"],
                "givenName": [name[0]],
                "lastLogoff": ['0'],
                "lastLogon": ['0'],
                "logonCount": ['0'],
                "mail": [f"{name[0]}.{name[1]}@somedomain.com"],
                "name": [f"TEST {user}"],
                "objectClass": [
                    'top',
                    'person',
                    'organizationalPerson',
                    'user'
                ],
                "sAMAccountName": [f"{name[0]}.{name[1]}"],
                # Normal Account, don't expire password
                "userAccountControl": ['66048']
            })
        user_list.append(user_obj)
    return user_list


def handler(event, context):
    # http://listofrandomnames.com/index.cfm
    test_users = [
        "Grace Ogden",
        "Christopher Morgan",
        "Theresa Clarkson",
        "Grace Baker",
        "Justin Dickens",
        "Adam Bond",
        "John Terry",
        "William Paige",
        "Stephanie Buckland",
        "Elizabeth Mathis"
    ]
    users = generate_test_user_objects(test_users)
    return LdapMaintainer().disable_users(users)
