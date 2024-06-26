# Licensed under the terms of the GNU GPL License version 2

import datetime
import logging
import logging.handlers
import os
import sys
import urllib.parse
from functools import wraps

import flask
import flask_wtf
import munch
import six
import wtforms as wtf
from flask_oidc import OpenIDConnect
from flask_wtf.file import FileRequired
from kerneltest_messages import ReleaseEditV1, ReleaseNewV1, UploadNewV1
from sqlalchemy.exc import SQLAlchemyError

import kerneltest.dbtools as dbtools
import kerneltest.messaging as messaging
import kerneltest.proxy

__version__ = "1.3.0"

APP = flask.Flask(__name__)
APP.config.from_object("kerneltest.default_config")
if "KERNELTEST_CONFIG" in os.environ:  # pragma: no cover
    APP.config.from_envvar("KERNELTEST_CONFIG")

# Set up FAS extension

OIDC = OpenIDConnect(APP, credentials_store=flask.session)

# Set up the logger
## Send emails for big exception
mail_admin = APP.config.get("MAIL_ADMIN", None)
if mail_admin and not APP.debug:
    MAIL_HANDLER = logging.handlers.SMTPHandler(
        APP.config.get("SMTP_SERVER", "127.0.0.1"),
        "nobody@fedoraproject.org",
        mail_admin,
        "Kerneltest-harness error",
    )
    MAIL_HANDLER.setFormatter(
        logging.Formatter(
            """
        Message type:       %(levelname)s
        Location:           %(pathname)s:%(lineno)d
        Module:             %(module)s
        Function:           %(funcName)s
        Time:               %(asctime)s

        Message:

        %(message)s
    """
        )
    )
    MAIL_HANDLER.setLevel(logging.ERROR)
    APP.logger.addHandler(MAIL_HANDLER)


# Log to stderr as well
STDERR_LOG = logging.StreamHandler(sys.stderr)
STDERR_LOG.setLevel(logging.INFO)
APP.logger.addHandler(STDERR_LOG)

APP.wsgi_app = kerneltest.proxy.ReverseProxied(APP.wsgi_app)

SESSION = dbtools.create_session(APP.config["DB_URL"])


@APP.before_request
def set_session():  # pragma: no-cover
    """Set the flask session as permanent."""
    flask.session.permanent = True

    if OIDC.user_loggedin:
        if not hasattr(flask.session, "fas_user") or not flask.session.fas_user:
            flask.session.fas_user = munch.Munch(
                {
                    "username": OIDC.user_getfield("nickname"),
                    "email": OIDC.user_getfield("email") or "",
                    "timezone": OIDC.user_getfield("zoneinfo"),
                    "groups": OIDC.user_getfield("groups"),
                    "cla_done": "signed_fpca" in (OIDC.user_getfield("groups") or []),
                }
            )
        flask.g.fas_user = flask.session.fas_user

    else:
        flask.session.fas_user = None
        flask.g.fas_user = None


## Exception generated when uploading the results into the database.


class InvalidInputException(Exception):
    """Exception raised when the user provided an invalid test result file."""

    pass


## Generic functions


def parseresults(log):
    """Parse the result of the kernel tests."""
    testdate = None
    testset = None
    testkver = None
    testrel = None
    testresult = None
    failedtests = None
    for line in log:
        line = line.decode()
        if "Date: " in line:
            testdate = line.replace("Date: ", "", 1).rstrip("\n")
            APP.logger.warn(testdate)
        elif "Test set: " in line:
            testset = line.replace("Test set: ", "", 1).rstrip("\n")
        elif "Kernel: " in line:
            testkver = line.replace("Kernel: ", "", 1).rstrip("\n")
        elif "Release: " in line:
            testrel = line.replace("Release: ", "", 1).rstrip("\n")
        elif "Result: " in line:
            testresult = line.replace("Result: ", "", 1).rstrip("\n")
        elif "Failed Tests: " in line:
            failedtests = line.replace("Failed Tests: ", "", 1).rstrip("\n")
        elif "========" in line:
            break
        # else:
        # APP.logger.info("No match found for: %s", line)
    return testdate, testset, testkver, testrel, testresult, failedtests


def upload_results(test_result, username, authenticated=False):
    """Actually try to upload the results into the database."""
    allowed_file(test_result)

    logdir = APP.config.get("LOG_DIR", "logs")
    if not os.path.exists(logdir) and not os.path.isdir(logdir):
        os.mkdir(logdir)
    try:
        (testdate, testset, testkver, testrel, testresult, failedtests) = parseresults(test_result)
        APP.logger.error(testkver)
    except Exception as err:
        APP.logger.error(err)
        raise InvalidInputException("Could not parse these results") from err

    if not testkver:
        raise InvalidInputException("Could not parse these results")

    relarch = testkver.split(".")
    fver = relarch[-2].replace("fc", "", 1)
    testarch = relarch[-1]
    # Work around for F19 and older kver conventions
    if testarch == "PAE":
        testarch = "i686+PAE"
        fver = relarch[-3].replace("fc", "", 1)

    if is_authenticated():
        username = flask.g.fas_user.username

    test = dbtools.KernelTest(
        tester=username,
        testdate=testdate,
        testset=testset,
        kver=testkver,
        fver=fver,
        testarch=testarch,
        testrel=testrel,
        testresult=testresult,
        failedtests=failedtests,
        authenticated=authenticated,
    )

    SESSION.add(test)
    SESSION.flush()

    if authenticated:
        msg = UploadNewV1(
            body=dict(
                agent=username,
                test=test.to_json(),
            )
        )

        messaging.publish(msg)

    filename = "%s.log" % test.testid
    test_result.seek(0)
    test_result.save(os.path.join(logdir, filename))

    return test


## Flask specific utility function


def is_authenticated():
    """Returns whether the user is currently authenticated or not."""
    return hasattr(flask.g, "fas_user") and flask.g.fas_user is not None


def is_admin(user):
    """Is the user an admin."""
    if not user:
        return False

    if not user.cla_done:
        return False

    admins = APP.config["ADMIN_GROUP"]
    if isinstance(admins, six.string_types):
        admins = [admins]
    admins = set(admins)

    return len(admins.intersection(set(user.groups))) > 0


def safe_redirect_back(next=None, fallback=("index", {})):
    """Safely redirect the user to its previous page."""
    targets = []
    if next:  # pragma: no cover
        targets.append(next)
    if "next" in flask.request.args and flask.request.args["next"]:  # pragma: no cover
        targets.append(flask.request.args["next"])
    targets.append(flask.url_for(fallback[0], **fallback[1]))
    for target in targets:
        if is_safe_url(target):
            return flask.redirect(target)


def is_safe_url(target):
    """Checks that the target url is safe and sending to the current
    website not some other malicious one.
    """
    ref_url = urllib.parse.urlparse(flask.request.host_url)
    test_url = urllib.parse.urlparse(urllib.parse.urljoin(flask.request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def admin_required(function):
    """Flask decorator to ensure that the user is logged in."""

    @wraps(function)
    def decorated_function(*args, **kwargs):
        """Wrapped function actually checking if the user is logged in."""
        if not is_authenticated():
            return flask.redirect(flask.url_for("login", next=flask.request.url))
        elif not is_admin(flask.g.fas_user):
            flask.flash("You are not an admin", "error")
            return flask.redirect(flask.url_for("index"))
        return function(*args, **kwargs)

    return decorated_function


def allowed_file(input_file):
    """Validate the uploaded file.
    Checks if its extension and mimetype are within the lists of
    mimetypes and extensions allowed.
    """
    # Mimetype allowed for file to upload
    allowed_types = APP.config.get("ALLOWED_MIMETYPES", [])
    APP.logger.info("input submitted with mimetype: %s" % input_file.mimetype)
    if input_file.mimetype not in allowed_types:
        raise InvalidInputException("Invalid input submitted: %s" % input_file.mimetype)


@APP.context_processor
def inject_variables():
    """Inject some variables in every templates."""
    releases = dbtools.getcurrentreleases(SESSION)
    rawhide = dbtools.getrawhide(SESSION)
    admin = False
    if is_authenticated():
        admin = is_admin(flask.g.fas_user)

    return dict(
        date=datetime.datetime.utcnow().strftime("%a %b %d %Y %H:%M"),
        releases=releases,
        rawhide=rawhide,
        version=__version__,
        is_admin=admin,
    )


@APP.teardown_request
def shutdown_session(exception=None):
    """Remove the DB session at the end of each request."""
    SESSION.remove()


## The flask application itself


@APP.route("/")
def index():
    """Display the index page."""
    releases = dbtools.getcurrentreleases(SESSION)
    rawhide = dbtools.getrawhide(SESSION)

    test_matrix = []
    for release in releases:
        arches = dbtools.getarches(SESSION, release.releasenum)
        for arch in arches:
            results = dbtools.getlatest(SESSION, release.releasenum, arch[0])
            if results:
                test_matrix.append(results)

    return flask.render_template(
        "index.html",
        releases=releases,
        rawhide=rawhide,
        test_matrix=test_matrix,
    )


@APP.route("/release/<release>")
def release(release):
    """Display page with information about a specific release."""
    kernels = dbtools.getkernelsbyrelease(SESSION, release)

    return flask.render_template(
        "release.html",
        release=release,
        kernels=kernels,
    )


@APP.route("/kernel/<kernel>")
def kernel(kernel):
    """Display page with information about a specific kernel."""
    tests = dbtools.getresultsbykernel(SESSION, kernel)

    return flask.render_template(
        "kernel.html",
        kernel=kernel,
        tests=tests,
    )


@APP.route("/logs/<logid>")
def logs(logid):
    """Display logs of a specific test run."""
    logdir = APP.config.get("LOG_DIR", "logs")
    return flask.send_from_directory(logdir, "%s.log" % logid)


@APP.route("/stats")
def stats():
    """Display some stats about the data gathered."""
    stats = dbtools.get_stats(SESSION)

    return flask.render_template(
        "stats.html",
        stats=stats,
    )


@APP.route("/upload/", methods=["GET", "POST"])
@OIDC.require_login
def upload():
    """Display the page where new results can be uploaded."""
    form = UploadForm()
    if form.validate_on_submit():
        test_result = form.test_result.data
        username = flask.g.fas_user.username

        if username == "kerneltest":
            flask.flash(
                "The `kerneltest` username is reserved, you are not " "allowed to use it", "error"
            )
            return flask.redirect(flask.url_for("upload"))

        try:
            tests = upload_results(test_result, username, authenticated=is_authenticated())
            SESSION.commit()
            flask.flash("Upload successful!")
        except InvalidInputException as err:
            APP.logger.error(err)
            flask.flash(str(err))
            return flask.redirect(flask.url_for("upload"))
        except SQLAlchemyError as err:
            APP.logger.exception(err)
            flask.flash("Could not save the data in the database")
            SESSION.rollback()
            return flask.redirect(flask.url_for("upload"))
        except OSError as err:
            APP.logger.exception(err)
            SESSION.delete(tests)
            SESSION.commit()
            flask.flash("Could not save the result file")
            return flask.redirect(flask.url_for("upload"))

    return flask.render_template(
        "upload.html",
        form=form,
    )


@APP.route("/upload/autotest", methods=["POST"])
def upload_autotest():
    """Specific endpoint for some clients to upload their results."""
    form = ApiUploadForm(meta={"csrf": False})
    httpcode = 200

    if form.validate_on_submit():
        test_result = form.test_result.data
        api_token = form.api_token.data

        if api_token is None or api_token != APP.config.get("API_KEY", None):
            output = {"error": "Invalid api_token provided"}
            jsonout = flask.jsonify(output)
            jsonout.status_code = 401
            return jsonout

        try:
            tests = upload_results(test_result, "kerneltest", authenticated=True)
            SESSION.commit()
            output = {"message": "Upload successful!"}
        except InvalidInputException as err:
            APP.logger.error(err)
            output = {"error": "Invalid input file"}
            httpcode = 400
        except SQLAlchemyError as err:
            APP.logger.exception(err)
            output = {"error": "Could not save data in the database"}
            httpcode = 500
        except OSError as err:
            APP.logger.exception(err)
            SESSION.delete(tests)
            SESSION.commit()
            output = {"error": "Could not save the result file"}
            httpcode = 500
    else:
        httpcode = 400
        output = {"error": "Invalid request", "messages": form.errors}

    jsonout = flask.jsonify(output)
    jsonout.status_code = httpcode
    return jsonout


@APP.route("/upload/anonymous", methods=["POST"])
def upload_anonymous():
    """Specific endpoint for some clients to upload their results."""
    form = UploadForm(meta={"csrf": False})
    httpcode = 200

    if form.validate_on_submit():
        test_result = form.test_result.data
        username = form.username.data

        if is_authenticated():
            username = flask.g.fas_user.username

        if username == "kerneltest":
            output = {
                "error": "The `kerneltest` username is reserved, you " "are not allowed to use it"
            }
            jsonout = flask.jsonify(output)
            jsonout.status_code = 401
            return jsonout

        try:
            tests = upload_results(test_result, username, authenticated=is_authenticated())
            SESSION.commit()
            output = {"message": "Upload successful!"}
        except InvalidInputException as err:
            APP.logger.error(err)
            output = {"error": "Invalid input file"}
            httpcode = 400
        except SQLAlchemyError as err:
            APP.logger.exception(err)
            output = {"error": "Could not save data in the database"}
            httpcode = 500
        except OSError as err:
            APP.logger.exception(err)
            SESSION.delete(tests)
            SESSION.commit()
            output = {"error": "Could not save the result file"}
            httpcode = 500
    else:
        httpcode = 400
        output = {"error": "Invalid request", "messages": form.errors}

    jsonout = flask.jsonify(output)
    jsonout.status_code = httpcode
    return jsonout


@APP.route("/login", methods=["GET", "POST"])
@OIDC.require_login
def login():
    """Login mechanism for this application."""
    next_url = None
    if "next" in flask.request.args:
        if is_safe_url(flask.request.args["next"]):
            next_url = flask.request.args["next"]

    if not next_url or next_url == flask.url_for(".login"):
        next_url = flask.url_for(".index")

    return safe_redirect_back(next_url)


@APP.route("/logout")
@OIDC.require_login
def logout():
    """Log out if the user is logged in other do nothing.
    Return to the index page at the end.
    """
    next_url = flask.url_for("index")
    if "next" in flask.request.values:
        if is_safe_url(flask.request.values["next"]):
            next_url = flask.request.values["next"]

    if next_url == flask.url_for("logout"):
        next_url = flask.url_for("index")
    if hasattr(flask.g, "fas_user") and flask.g.fas_user is not None:
        OIDC.logout()
        flask.flash("You are no longer logged-in")
    return flask.redirect(next_url)


## Admin section


@APP.route("/admin/new", methods=("GET", "POST"))
@admin_required
def admin_new_release():
    form = ReleaseForm()
    if form.validate_on_submit():
        release = dbtools.Release()
        SESSION.add(release)
        form.populate_obj(obj=release)
        SESSION.commit()

        msg = ReleaseNewV1(
            body=dict(
                agent=flask.g.fas_user.username,
                release=release.to_json(),
            )
        )
        messaging.publish(msg)

        flask.flash('Release "%s" added' % release.releasenum)
        return flask.redirect(flask.url_for("index"))
    return flask.render_template("release_new.html", form=form, submit_text="Create release")


@APP.route("/admin/<relnum>/edit", methods=("GET", "POST"))
@admin_required
def admin_edit_release(relnum):
    release = dbtools.get_release(SESSION, relnum)
    if not release:
        flask.flash("No release %s found" % relnum)
        return flask.redirect(flask.url_for("index"))

    form = ReleaseForm(obj=release)
    if form.validate_on_submit():
        form.populate_obj(obj=release)
        SESSION.commit()

        msg = ReleaseEditV1(
            body=dict(
                agent=flask.g.fas_user.username,
                release=release.to_json(),
            )
        )
        messaging.publish(msg)

        flask.flash('Release "%s" updated' % release.releasenum)
        return flask.redirect(flask.url_for("index"))
    return flask.render_template(
        "release_new.html", form=form, release=release, submit_text="Edit release"
    )


## Form used to upload new results


class UploadForm(flask_wtf.FlaskForm):
    """Form used to upload the results of kernel tests."""

    username = wtf.StringField("Username", default="anon")
    test_result = wtf.FileField("Result file", validators=[FileRequired()])


class ApiUploadForm(flask_wtf.FlaskForm):
    """Form used to upload the results of kernel tests via the api."""

    username = wtf.StringField("Username", default="anon")
    api_token = wtf.StringField("API token", validators=[wtf.validators.DataRequired()])
    test_result = wtf.FileField("Result file", validators=[FileRequired()])


class ReleaseForm(flask_wtf.FlaskForm):
    """Form used to create or edit release in the database."""

    releasenum = wtf.IntegerField(
        "Release number <span class='error'>*</span>", validators=[wtf.validators.DataRequired()]
    )
    support = wtf.SelectField(
        "Support <span class='error'>*</span>",
        validators=[wtf.validators.DataRequired()],
        choices=[
            ("RAWHIDE", "Rawhide"),
            ("TEST", "Test"),
            ("RELEASE", "Release"),
            ("RETIRED", "Retired"),
        ],
    )
