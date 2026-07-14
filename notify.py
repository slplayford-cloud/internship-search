"""Push notifications through ntfy (https://ntfy.sh).

The one place that talks to ntfy. A message is an HTTP POST to <server>/<topic> with the message
as the body; any phone subscribed to that topic in the ntfy app receives it.

Anyone who knows the topic name can read the topic on the public server, so the topic name is the
only thing keeping the feed private: make it unguessable, and keep message bodies free of anything
you wouldn't publish. That is why the tracker sends only a count of new listings.
"""

import os
import sys

import requests

DEFAULT_SERVER = "https://ntfy.sh"
PLACEHOLDER_TOPIC = "CHANGE-ME-to-an-unguessable-topic"
TIMEOUT = 15


def send(
    message: str,
    *,
    title: str | None = None,
    priority: str | None = None,
    tags: str | None = None,
    click: str | None = None,
) -> bool:
    """Publish a message to the configured topic. Returns whether it was delivered.

    Never raises: a failed notification must not take down the caller.
    """
    server = os.getenv("NTFY_SERVER", DEFAULT_SERVER).rstrip("/")
    topic = os.getenv("NTFY_TOPIC")
    token = os.getenv("NTFY_TOKEN")

    if not topic or topic == PLACEHOLDER_TOPIC:
        print(
            "ntfy: set NTFY_TOPIC to an unguessable topic name (see .env.example); nothing sent",
            file=sys.stderr,
        )
        return False

    # A typo'd server must not put the topic and token on the wire in cleartext.
    if not server.startswith("https://") and os.getenv("NTFY_ALLOW_INSECURE") != "1":
        print(
            f"ntfy: refusing to send over insecure {server!r}; "
            "use https, or set NTFY_ALLOW_INSECURE=1 for a trusted local server",
            file=sys.stderr,
        )
        return False

    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags,
        "Click": click,
        "Authorization": f"Bearer {token}" if token else None,
    }

    try:
        response = requests.post(
            f"{server}/{topic}",
            data=message.encode("utf-8"),
            headers={key: value for key, value in headers.items() if value},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"ntfy: {error}", file=sys.stderr)
        return False

    return True
