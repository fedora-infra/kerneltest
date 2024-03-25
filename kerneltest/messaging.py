import backoff
from fedora_messaging.api import publish as fm_publish
from fedora_messaging.exceptions import ConnectionException, PublishTimeout


@backoff.on_exception(
    backoff.expo,
    (ConnectionException, PublishTimeout),
    max_tries=3,
)
def publish(msg):
    fm_publish(msg)
