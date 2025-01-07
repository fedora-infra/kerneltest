# Licensed under the terms of the GNU GPL License version 2


"""
kerneltest tests.
"""

__requires__ = ["SQLAlchemy >= 0.7"]
import os
import sys
import time
import unittest
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import kerneltest.dbtools as dbtools

# DB_PATH = 'sqlite:///:memory:'
## A file database is required to check the integrity, don't ask
DB_PATH = "sqlite:////tmp/test.sqlite"
FAITOUT_URL = "http://faitout.fedorainfracloud.org/"

if os.environ.get("BUILD_ID"):
    try:
        import requests

        req = requests.get(f"{FAITOUT_URL}/new")
        if req.status_code == 200:
            DB_PATH = req.text
            print(f"Using faitout at: {DB_PATH}")
    except Exception:
        pass


class FakeFasUser:
    """Fake FAS user used for the tests."""

    id = 100
    username = "pingou"
    cla_done = True
    groups = ["packager", "signed_fpca"]
    email = "pingou@fp.o"


@contextmanager
def user_set(client, user):
    """Set the provided user as fas_user in the provided application."""

    with client.session_transaction() as session:
        session["oidc_auth_token"] = {
            "token_type": "Bearer",
            "access_token": "dummy_access_token",
            "refresh_token": "dummy_refresh_token",
            "expires_in": "3600",
            "expires_at": int(time.time()) + 3600,
        }
        session["oidc_auth_profile"] = {
            "nickname": user.username,
            "email": user.email,
            "zoneinfo": None,
            "groups": user.groups,
        }
    yield


def message_result(
    tester=None,
    testdate="Thu Apr 24 11:48:35 CDT 2014",
    release="Fedora release 19 (Schrodingers Cat)",
):
    # currently the only differences between the 4 test logs we use is the
    # date, and release fields. should expand this to make the tests better
    return {
        "agent": tester,
        "test": {
            "arch": "x86_64",
            "authenticated": True,
            "failed_tests": "./default/paxtest",
            "fedora_version": "20",
            "kernel_version": "3.14.1-200.fc20.x86_64",
            "release": release,
            "result": "FAIL",
            "testdate": testdate,
            "tester": tester,
            "testset": "default",
        },
    }


class Modeltests(unittest.TestCase):
    """Model tests."""

    def __init__(self, method_name="runTest"):
        """Constructor."""
        unittest.TestCase.__init__(self, method_name)
        self.session = None

    # pylint: disable=C0103
    def setUp(self):
        """Set up the environnment, ran before every tests."""
        if "///" in DB_PATH:
            dbfile = DB_PATH.split("///")[1]
            if os.path.exists(dbfile):
                os.unlink(dbfile)
        self.session = dbtools.create_session(DB_PATH, debug=False, create_table=True)

    # pylint: disable=C0103
    def tearDown(self):
        """Remove the test.db database if there is one."""
        if "///" in DB_PATH:
            dbfile = DB_PATH.split("///")[1]
            if os.path.exists(dbfile):
                os.unlink(dbfile)

        self.session.rollback()
        self.session.close()


if __name__ == "__main__":
    SUITE = unittest.TestLoader().loadTestsFromTestCase(Modeltests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
