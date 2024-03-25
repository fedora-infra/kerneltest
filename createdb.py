#!/usr/bin/python

from __future__ import print_function

from sqlalchemy.exc import SQLAlchemyError
import kerneltest.app as app
import kerneltest.dbtools as dbtools

dbtools.create_session(app.APP.config["DB_URL"], debug=True, create_table=True)

## Add current supported releases
SESSION = dbtools.create_session(app.APP.config["DB_URL"], debug=True)

release = dbtools.Release(
    releasenum="24",
    support="RELEASE",
)
SESSION.add(release)

release = dbtools.Release(
    releasenum="25",
    support="RELEASE",
)
SESSION.add(release)

release = dbtools.Release(
    releasenum="26",
    support="RELEASE",
)
SESSION.add(release)

release = dbtools.Release(
    releasenum="27",
    support="RAWHIDE",
)
SESSION.add(release)

try:
    SESSION.commit()
except SQLAlchemyError as err:
    print(err)
