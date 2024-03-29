""" This is an example kerneltest configuration for fedmsg.
By convention, it is normally installed as ``/etc/fedmsg.d/kernel.py``

For Fedora Infrastructure, our own version of this file is kept in
``puppet/modules/fedmsg/templates/fedmsg.d/``

It needs to be globally available so remote consumers know how to find the
kerneltest producer (wsgi process).
"""

import socket

hostname = socket.gethostname().split(".")[0]

config = dict(
    endpoints={
        "kerneltest.%s"
        % hostname: [
            "tcp://127.0.0.1:3005",
        ],
    },
)
