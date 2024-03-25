# Licensed under the terms of the GNU GPL License version 2

"""
kerneltest tests.
"""

__requires__ = ["SQLAlchemy >= 0.7"]

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pathlib import Path

from fedora_messaging import testing as fml_testing
from kerneltest_messages import ReleaseEditV1, ReleaseNewV1, UploadNewV1

import kerneltest.app as app
from tests import FakeFasUser, Modeltests, message_result, user_set


class KerneltestTests(Modeltests):
    """kerneltest tests."""

    def setUp(self):
        """Set up the environnment, ran before every tests."""
        super().setUp()

        app.APP.config["TESTING"] = True
        app.SESSION = self.session
        self.app = app.APP.test_client()

    def test_upload_results_loggedin(self):
        """Test the app.upload_results function."""
        folder = Path(__file__).parent
        filename = "1.log"

        user = FakeFasUser()
        with user_set(self.app, user):
            output = self.app.get("/upload/", follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertTrue(
                (b'<td><input id="test_result" name="test_result" ' b'required type="file"></td>')
                in output.data
            )

            csrf_token = (
                output.data.decode("utf-8")
                .split('name="csrf_token" type="hidden" value="')[1]
                .split('">')[0]
            )

            # Valid upload via the UI
            data = {
                "test_result": (folder / filename).open("rb"),
                "username": "pingou",
                "csrf_token": csrf_token,
            }
            with fml_testing.mock_sends(UploadNewV1(message_result(tester="pingou"))):
                output = self.app.post("/upload/", data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertTrue(b'<li class="message">Upload successful!</li>' in output.data)

            # Invalid file upload
            filename = "invalid.log"
            data = {
                "test_result": (folder / filename).open("rb"),
                "username": "pingou",
                "csrf_token": csrf_token,
            }
            output = self.app.post("/upload/", data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)

            # Invalid file upload
            filename = "invalid.log"
            data = {
                "test_result": (folder / filename).open("rb"),
                "username": "pingou",
                "csrf_token": csrf_token,
            }
            output = self.app.post("/upload/", data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertTrue(
                b'<li class="message">Could not parse these results</li>' in output.data
            )

        # Invalid username
        user = FakeFasUser()
        user.username = "kerneltest"
        with user_set(self.app, user):
            filename = "invalid.log"
            data = {
                "test_result": (folder / filename).open("rb"),
                "username": "pingou",
                "csrf_token": csrf_token,
            }
            output = self.app.post("/upload/", data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertTrue(
                b'<li class="error">The `kerneltest` username is reserved, '
                b"you are not allowed to use it</li>" in output.data
            )

    def test_upload_results_anonymous(self):
        """Test the app.upload_results function for an anonymous user."""
        folder = Path(__file__).parent
        filename = "2.log"

        output = self.app.get("/upload/")
        self.assertEqual(output.status_code, 302)
        self.assertTrue(b"<title>Redirecting...</title>" in output.data)

        output = self.app.get("/upload/anonymous")
        self.assertEqual(output.status_code, 405)
        self.assertTrue(b"<title>405 Method Not Allowed</title>" in output.data)

        data = {
            "test_result": (folder / filename).open("rb"),
            "username": "pingou",
        }
        output = self.app.post("/upload/", data=data)
        self.assertEqual(output.status_code, 302)
        self.assertTrue(b"<title>Redirecting...</title>" in output.data)

        # Invalid request
        data = {
            "username": "pingou",
        }
        output = self.app.post("/upload/anonymous", data=data)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        exp = {"error": "Invalid request", "messages": {"test_result": ["This field is required."]}}
        self.assertEqual(data, exp)

        # Invalid username

        data = {
            "test_result": (folder / filename).open("rb"),
            "username": "kerneltest",
        }
        output = self.app.post("/upload/anonymous", data=data)
        self.assertEqual(output.status_code, 401)
        data = json.loads(output.data)
        exp = {"error": "The `kerneltest` username is reserved, you are " "not allowed to use it"}
        self.assertEqual(data, exp)

        # Valid and successful upload
        data = {
            "test_result": (folder / filename).open("rb"),
            "username": "pingou",
        }
        output = self.app.post("/upload/anonymous", data=data)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertEqual(data, {"message": "Upload successful!"})

        # Invalid file upload
        filename = "invalid.log"
        data = {
            "test_result": (folder / filename).open("rb"),
            "username": "ano",
        }
        output = self.app.post("/upload/anonymous", data=data)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        exp = {"error": "Invalid input file"}
        self.assertEqual(data, exp)

        # Invalid mime type uploaded
        filename = "denied.png"
        data = {
            "test_result": (folder / filename).open("rb"),
            "username": "ano",
        }
        output = self.app.post("/upload/anonymous", data=data)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        exp = {"error": "Invalid input file"}
        self.assertEqual(data, exp)

    def test_upload_results_autotest(self):
        """Test the app.upload_results function for the autotest user."""
        folder = Path(__file__).parent
        filename = "3.log"

        output = self.app.get("/upload/autotest")
        self.assertEqual(output.status_code, 405)
        self.assertTrue(b"<title>405 Method Not Allowed</title>" in output.data)

        # Missing the api_token field
        data = {
            "test_result": (folder / filename).open("rb"),
            "username": "kerneltest",
        }
        output = self.app.post("/upload/autotest", data=data)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        exp = {"error": "Invalid request", "messages": {"api_token": ["This field is required."]}}
        self.assertEqual(data, exp)

        # Invalid api_token
        data = {
            "test_result": (folder / filename).open("rb"),
            "username": "kerneltest",
            "api_token": "foobar",
        }
        output = self.app.post("/upload/autotest", data=data)
        self.assertEqual(output.status_code, 401)
        data = json.loads(output.data)
        exp = {"error": "Invalid api_token provided"}
        self.assertEqual(data, exp)

        # Valid api_token
        app.APP.config["API_KEY"] = "api token for the tests"

        data = {
            "test_result": (folder / filename).open("rb"),
            "username": "kerneltest",
            "api_token": "api token for the tests",
        }
        with fml_testing.mock_sends(UploadNewV1(message_result(tester="kerneltest"))):
            output = self.app.post("/upload/autotest", data=data)

        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        exp = {"message": "Upload successful!"}
        self.assertEqual(data, exp)

        # Second valid upload
        filename = "4.log"
        data = {
            "test_result": (folder / filename).open("rb"),
            "username": "kerneltest",
            "api_token": "api token for the tests",
        }
        with fml_testing.mock_sends(
            UploadNewV1(
                message_result(
                    testdate="Thu Apr 24 15:35:20 CDT 2014",
                    release="Fedora release 19 (Schrödinger’s Cat)",
                    tester="kerneltest",
                )
            )
        ):
            output = self.app.post("/upload/autotest", data=data)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        exp = {"message": "Upload successful!"}
        self.assertEqual(data, exp)

        # Invalid file upload
        filename = "invalid.log"
        data = {
            "test_result": (folder / filename).open("rb"),
            "username": "kerneltest",
            "api_token": "api token for the tests",
        }
        output = self.app.post("/upload/autotest", data=data)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        exp = {"error": "Invalid input file"}
        self.assertEqual(data, exp)

    def test_stats(self):
        """Test the stats method."""
        self.test_upload_results_autotest()
        self.test_upload_results_anonymous()
        self.test_upload_results_loggedin()

        output = self.app.get("/stats")
        data = output.data.decode("utf-8").split("\n")
        # for idx, item in enumerate(data):
        #     print(f'{idx} -- `{item}`')
        self.assertEqual(data[63], "    <th>Number of tests</th>")
        self.assertEqual(data[64], "    <td>4</td>")
        self.assertEqual(data[68], "    <td>1</td>")
        self.assertEqual(data[72], "    <td>1</td>")
        self.assertEqual(output.data.count(b"<td>3.14.1-200.fc20.x86_64</td>"), 1)

    def test_index(self):
        """Test the index method."""
        self.test_upload_results_autotest()
        self.test_upload_results_anonymous()
        self.test_upload_results_loggedin()
        self.test_admin_new_release()

        output = self.app.get("/")
        self.assertTrue(b"<a href='/kernel/3.14.1-200.fc20.x86_64'>" in output.data)
        self.assertTrue(b"<a href='/release/20'>" in output.data)

    def test_release(self):
        """Test the release method."""
        self.test_upload_results_autotest()
        self.test_upload_results_anonymous()
        self.test_upload_results_loggedin()
        self.test_admin_new_release()

        output = self.app.get("/release/20")
        self.assertTrue(b"<a href='/kernel/3.14.1-200.fc20.x86_64'>" in output.data)
        self.assertTrue(b"<h1>Kernels Tested for Fedora </h1>" in output.data)

    def test_kernel(self):
        """Test the kernel method."""
        self.test_upload_results_autotest()
        self.test_upload_results_anonymous()
        self.test_upload_results_loggedin()
        self.test_admin_new_release()

        output = self.app.get("/kernel/3.14.1-200.fc20.x86_64")
        self.assertEqual(output.data.decode("utf-8").count('<img src="/static/Denied.png" />'), 4)
        self.assertTrue(b"<a href='/logs/1'>" in output.data)
        self.assertTrue(b"<a href='/logs/2'>" in output.data)
        self.assertTrue(b"<a href='/logs/3'>" in output.data)
        self.assertTrue(b"<a href='/logs/4'>" in output.data)

    def test_is_safe_url(self):
        """Test the is_safe_url function."""
        import flask

        lcl_app = flask.Flask("kerneltest")

        with lcl_app.test_request_context():
            self.assertTrue(app.is_safe_url("http://localhost"))
            self.assertTrue(app.is_safe_url("https://localhost"))
            self.assertTrue(app.is_safe_url("http://localhost/test"))
            self.assertFalse(app.is_safe_url("http://fedoraproject.org/"))
            self.assertFalse(app.is_safe_url("https://fedoraproject.org/"))

    def test_admin_new_release(self):
        """Test the admin_new_release function."""
        user = FakeFasUser()
        user.groups = []
        user.cla_done = False
        with user_set(self.app, user):
            output = self.app.get("/admin/new", follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertTrue(b'<li class="error">You are not an admin</li>' in output.data)

        user = FakeFasUser()
        user.groups = []
        with user_set(self.app, user):
            output = self.app.get("/admin/new", follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertTrue(b'<li class="error">You are not an admin</li>' in output.data)

        user = FakeFasUser()
        user.groups.append("sysadmin-main")
        with user_set(self.app, user):
            output = self.app.get("/admin/new")
            self.assertEqual(output.status_code, 200)
            self.assertTrue(b"<title> New release" in output.data)
            print(output.data)
            self.assertTrue(b'<label for="releasenum">Release number' in output.data)

            csrf_token = (
                output.data.decode("utf-8")
                .split('name="csrf_token" type="hidden" value="')[1]
                .split('">')[0]
            )

            data = {
                "csrf_token": csrf_token,
                "releasenum": 20,
                "support": "RELEASE",
            }

            expected_message = {
                "agent": "pingou",
                "release": {"releasenum": 20, "support": "RELEASE"},
            }
            with fml_testing.mock_sends(ReleaseNewV1(expected_message)):
                output = self.app.post("/admin/new", data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertTrue(b'<li class="message">Release &#34;20&#34; added</li>' in output.data)
            self.assertTrue(b"<a href='/release/20'>" in output.data)
            self.assertTrue(b"<a href='/admin/20/edit'" in output.data)

    def test_admin_edit_release(self):
        """Test the admin_new_release function."""
        self.test_admin_new_release()

        user = FakeFasUser()
        user.groups.append("sysadmin-kernel")
        with user_set(self.app, user):
            output = self.app.get("/admin/21/edit", follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertTrue(b'<li class="message">No release 21 found</li>' in output.data)

            output = self.app.get("/admin/20/edit")
            self.assertEqual(output.status_code, 200)
            self.assertTrue(b"<h1> Release: 20 </h1>" in output.data)
            self.assertTrue(b'<form action="/admin/20/edit" method="POST">' in output.data)

            csrf_token = (
                output.data.decode("utf-8")
                .split('name="csrf_token" type="hidden" value="')[1]
                .split('">')[0]
            )

            data = {
                "csrf_token": csrf_token,
                "releasenum": 21,
                "support": "RAWHIDE",
            }

            expected_message = {
                "agent": "pingou",
                "release": {"releasenum": 21, "support": "RAWHIDE"},
            }
            with fml_testing.mock_sends(ReleaseEditV1(expected_message)):
                output = self.app.post("/admin/20/edit", data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertTrue(b'<li class="message">Release &#34;21&#34; updated</li>' in output.data)
            self.assertTrue(b"<a href='/release/21'>" in output.data)
            self.assertTrue(b"Fedora Rawhide" in output.data)
            self.assertTrue(b"<a href='/admin/21/edit'" in output.data)
            self.assertFalse(b"<a href='/release/20'>" in output.data)
            self.assertFalse(b"<a href='/admin/20/edit'" in output.data)

    def test_logs(self):
        """Test the logs method."""
        folder = os.path.dirname(os.path.abspath(__file__))
        app.APP.config["LOG_DIR"] = os.path.join(folder, "logs")

        self.test_upload_results_autotest()

        # Read the files uploaded
        filename = "3.log"
        full_path = os.path.join(folder, filename)
        with open(full_path, "rb") as stream:
            exp_1 = stream.read()

        filename = "4.log"
        full_path = os.path.join(folder, filename)
        with open(full_path, "rb") as stream:
            exp_2 = stream.read()

        # Compare what's uploaded and what's stored
        output = self.app.get("/logs/1")
        self.assertEqual(output.data, exp_1)

        output = self.app.get("/logs/2")
        self.assertEqual(output.data, exp_2)

    def test_is_admin(self):
        """Test the is_admin method."""
        self.assertFalse(app.is_admin(None))

        user = FakeFasUser()
        user.cla_done = False
        self.assertFalse(app.is_admin(user))

        user = FakeFasUser()
        user.groups = []
        self.assertFalse(app.is_admin(user))

        user = FakeFasUser()
        user.groups.append("sysadmin-main")
        self.assertTrue(app.is_admin(user))


if __name__ == "__main__":
    SUITE = unittest.TestLoader().loadTestsFromTestCase(KerneltestTests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
