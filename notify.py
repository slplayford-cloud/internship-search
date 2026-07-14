"""Push notifications through ntfy (https://ntfy.sh).

The one place that talks to ntfy. A message is an HTTP POST to <server>/<topic> with the message
as the body; any phone subscribed to that topic in the ntfy app receives it.

Anyone who knows the topic name can read the topic on the public server, so the topic name is the
only thing keeping the feed private: make it unguessable. Listing details are safe to send in full
since they're scraped from public GitHub READMEs anyway — just don't put anything else (notes,
credentials, etc.) in a message body you wouldn't want published.
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
    actions: list[dict] | None = None,
) -> bool:
    """Publish a message to the configured topic. Returns whether it was delivered.

    Never raises: a failed notification must not take down the caller.

    Uses ntfy's JSON publish format (POST to the server root, topic in the body) rather than the
    plain POST-to-/<topic> form, since `actions` — the notification's tappable buttons — is
    structured data that only the JSON format can carry cleanly.
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

    payload = {
        "topic": topic,
        "message": message,
        "title": title,
        "priority": priority,
        "tags": [tags] if tags else None,
        "click": click,
        "actions": actions,
    }
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        response = requests.post(
            server,
            json={key: value for key, value in payload.items() if value},
            headers=headers,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"ntfy: {error}", file=sys.stderr)
        return False

    return True
