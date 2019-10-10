import collections
import logging
import os

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

    def get_all_users(self):
        """Search LDAP and return all user objects."""
        return self.search("(&(objectCategory=person)(objectClass=user))")

    def add_users(self, user_obj):
        con = self.connect()
        results = []
        for user in user_obj:
            dn = f"cn={user['cn'][0].decode('utf-8')},CN=Users,{DOMAIN_BASE}"
            results.append(con.add_s(dn, ldap.modlist.addModlist(user)))
        return results


def byte_encode_user_map(input_map):
    for element in input_map:
        element_list = input_map[element]
        for i in range(len(element_list)):
            element_list[i] = element_list[i].encode('utf-8')
    return input_map


def generate_test_user_objects():
    user_list = []
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

    for user in test_users:
        name = user.split()
        user_list.append(byte_encode_user_map({
                "givenName": [name[0]],
                "name": [user],
                "cn": [user],
                "displayName": [f"Test account {user}"],
                "description": ["Test account"],
                "lastLogon": ['0'],
                "lastLogoff": ['0'],
                "logonCount": ['0'],
                "sAMAccountName": [f"{user[0]}.{user[1]}"],
                # Normal Account, don't expire password
                "userAccountControl": ['66048'],
                "objectClass": [
                    'top',
                    'person',
                    'organizationalPerson',
                    'user'
                ]
            }))
    return user_list


def handler(event, context):
    users = generate_test_user_objects()
    return LdapMaintainer().add_users(users)
