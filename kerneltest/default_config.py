# -*- coding: utf-8 -*-

import os

# Secret key used to generate the CRSF token, thus very private!
SECRET_KEY = '<change me before using me in prod>'

# URL used to connect to the database
DB_URL = 'sqlite:////var/tmp/kernel-test_dev.sqlite'

# Specify where the logs of the tests should be stored
LOG_DIR = 'logs'

# API key used to authenticate the autotest client, should be private as well
API_KEY = 'This is a secret only the cli knows about'

# Email of the admin that should receive the error emails
MAIL_ADMIN = None

# FAS group or groups (provided as a list) in which should be the admins
# of this application
ADMIN_GROUP = ['sysadmin-kernel', 'sysadmin-main']

# List of MIME types allowed for upload in the application
ALLOWED_MIMETYPES = ['text/plain']

# Restrict the size of content uploaded, this is 25Kb
MAX_CONTENT_LENGTH = 1024 * 25

# obviously, this needs to be changed for deployments
OIDC_CLIENT_SECRETS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "../tests", "client_secrets.json"
)

OIDC_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://id.fedoraproject.org/scope/groups",
    "https://id.fedoraproject.org/scope/agreements",
    "https://id.fedoraproject.org/scope/fas-attributes",
]
