#!/usr/bin/python

import argparse

parser = argparse.ArgumentParser(description="Run the Kernel test harness app")

parser.add_argument(
    "--host",
    default="127.0.0.1",
    help="Hostname to listen on. When set to 0.0.0.0 the server is available "
    "externally. Defaults to 127.0.0.1 making the it only visible on localhost",
)

parser.add_argument("--port", "-p", default=5000, help="Port for the flask application.")
parser.add_argument(
    "--cert", "-s", default=None, help="Filename of SSL cert for the flask application."
)
parser.add_argument(
    "--key",
    "-k",
    default=None,
    help="Filename of the SSL key for the flask application.",
)

args = parser.parse_args()

from kerneltest.app import APP

APP.debug = True
if args.cert and args.key:
    APP.run(host=args.host, port=int(args.port), ssl_context=(args.cert, args.key))
else:
    APP.run(host=args.host, port=int(args.port))
